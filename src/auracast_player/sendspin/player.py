"""The Sendspin player: takes audio from Music Assistant and hands it to the broadcast."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import TYPE_CHECKING, Protocol

from aiosendspin.client import ClientListener, SendspinClient
from aiosendspin.client.models import PairingSupport
from aiosendspin.models import AudioCodec, DeviceInfo, PlayerCommand, Roles
from aiosendspin.models.player import ClientHelloPlayerSupport, SupportedAudioFormat
from aiosendspin.models.types import GoodbyeReason
from aiosendspin.noise.trust_store import FileClientPairingStore

from ..audio.transmitter import BUFFER_BYTES
from ..config.state import PAIRING_FILE, load_identity, save_state
from ..constants import BIT_DEPTH, CHANNELS, SAMPLE_RATE
from .pairing import Pairing

if TYPE_CHECKING:
    from pathlib import Path

    from aiohttp import web
    from aiosendspin.client.models import AudioFormat
    from aiosendspin.models.core import ServerCommandPayload

    from ..config.options import Options
    from ..config.state import PlayerState

LOGGER = logging.getLogger(__name__)
LISTENER_STOP_TIMEOUT = 2.0
PLAYER_ROLE = Roles.PLAYER.value.partition("@")[0]


class AudioSink(Protocol):
    """Where the audio the server sends goes."""

    def feed(self, pcm: bytes) -> None:
        """Queue audio for playback."""

    def clear(self) -> None:
        """Drop queued audio, as the end of a stream or a seek asks."""


class SendspinPlayer:
    """Advertise a Sendspin player, and pass the audio it is sent to a transmitter."""

    def __init__(
        self,
        options: Options,
        state: PlayerState,
        state_dir: Path,
        transmitter: AudioSink,
        device_info: DeviceInfo | None = None,
    ) -> None:
        """
        Create the player; nothing is advertised until it is started.

        :param options: The add-on options.
        :param state: The state kept across restarts, updated as the server changes it.
        :param state_dir: The directory holding the player's state.
        :param transmitter: Where the received audio goes.
        :param device_info: The manufacturer and model shown for this player in the server.
        """
        self._options = options
        self._state = state
        self._state_dir = state_dir
        self._transmitter = transmitter
        self._device_info = device_info
        self._pairing = Pairing(allow_unpaired=options.allow_unpaired)
        self._client: SendspinClient | None = None
        self._listener: ClientListener | None = None
        self._tasks: set[asyncio.Task[None]] = set()

    async def start(self) -> None:
        """Start advertising the player and accepting servers."""
        identity = load_identity(self._state_dir)
        store = await FileClientPairingStore.open(self._state_dir / PAIRING_FILE)
        await self._pairing.configure(store, identity.peer_id)
        support = ClientHelloPlayerSupport(
            supported_formats=[
                SupportedAudioFormat(
                    codec=AudioCodec.PCM,
                    channels=CHANNELS,
                    sample_rate=SAMPLE_RATE,
                    bit_depth=BIT_DEPTH,
                )
            ],
            buffer_capacity=BUFFER_BYTES,
            supported_commands=[PlayerCommand.VOLUME, PlayerCommand.MUTE],
        )
        client = SendspinClient(
            identity=identity,
            client_name=self._options.player_name,
            roles=[Roles.PLAYER],
            pairing_store=store,
            player_support=support,
            device_info=self._device_info,
            pairing_support=PairingSupport(pairing_code_display=self._pairing.show_code),
            initial_volume=self._state.volume,
            initial_muted=self._state.muted,
            output_delay_ms=self._state.output_delay_ms,
            state_supported_commands=[PlayerCommand.SET_OUTPUT_DELAY],
        )
        client.add_audio_chunk_listener(self._on_audio_chunk)
        client.add_stream_end_listener(self._on_stream_dropped)
        client.add_stream_clear_listener(self._on_stream_dropped)
        client.add_server_command_listener(self._on_server_command)
        client.add_output_delay_listener(self._on_output_delay)
        self._client = client
        self._listener = ClientListener(
            client_id=identity.peer_id,
            on_connection=self._on_connection,
            client_name=self._options.player_name,
        )
        await self._listener.start()
        LOGGER.info(
            'Advertising "%s" over mDNS, waiting for Music Assistant', self._options.player_name
        )

    async def stop(self) -> None:
        """Disconnect the server first, then stop listening, so shutdown cannot wait on a client."""
        client, self._client = self._client, None
        if client is not None:
            # An add-on stops mostly to restart or update. Only a `restart` goodbye makes the
            # server keep redialling; any other reason leaves reconnecting to mDNS discovery.
            with contextlib.suppress(Exception):
                await asyncio.wait_for(
                    client.disconnect(GoodbyeReason.RESTART), LISTENER_STOP_TIMEOUT
                )
        listener, self._listener = self._listener, None
        if listener is not None:
            try:
                await asyncio.wait_for(listener.stop(), LISTENER_STOP_TIMEOUT)
            except TimeoutError:
                LOGGER.warning("Timed out stopping the Sendspin listener")

    async def _on_connection(self, websocket: web.WebSocketResponse) -> None:
        """Hand a server that connected in to the client, and hold the connection open."""
        client = self._client
        if client is None:
            await websocket.close()
            return
        gone = asyncio.Event()
        remove = client.add_disconnect_listener(gone.set)
        try:
            await client.attach_websocket(websocket)
            await gone.wait()
        finally:
            remove()

    def _on_audio_chunk(
        self, timestamp_us: int, audio: bytes, audio_format: AudioFormat, send_ahead: int
    ) -> None:
        """Queue a chunk of PCM for transmission."""
        self._transmitter.feed(audio)

    def _on_stream_dropped(self, roles: list[str] | None) -> None:
        """Drop queued audio when the stream ends or is cleared for this player."""
        if roles is None or any(role.partition("@")[0] == PLAYER_ROLE for role in roles):
            self._transmitter.clear()

    def _on_server_command(self, payload: ServerCommandPayload) -> None:
        """Apply a volume or mute command and report the new state back."""
        command = payload.player
        if command is None:
            return
        if command.command == PlayerCommand.VOLUME and command.volume is not None:
            self._state.volume = command.volume
        elif command.command == PlayerCommand.MUTE and command.mute is not None:
            self._state.muted = command.mute
        else:
            return
        save_state(self._state_dir, self._state)
        task = asyncio.get_running_loop().create_task(self._publish_state())
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    def _on_output_delay(self, delay_ms: float) -> None:
        """Remember a delay the server set, so the next start begins with it."""
        self._state.output_delay_ms = delay_ms
        save_state(self._state_dir, self._state)

    async def _publish_state(self) -> None:
        """Tell the connected server the player's volume and mute state."""
        client = self._client
        if client is None or not client.connected:
            return
        with contextlib.suppress(RuntimeError, OSError):
            await client.send_player_state(
                available=True, volume=self._state.volume, muted=self._state.muted
            )
