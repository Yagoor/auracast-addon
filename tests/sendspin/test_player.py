"""Tests for the Sendspin player's handling of server commands and pairing."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from aiosendspin.models import PlayerCommand
from aiosendspin.models.core import ServerCommandPayload
from aiosendspin.models.player import PlayerCommandPayload
from aiosendspin.models.types import GoodbyeReason
from aiosendspin.noise import Identity

from auracast_player.audio.pcm import FRAME_BYTES
from auracast_player.audio.transmitter import Transmitter
from auracast_player.config.options import parse_options
from auracast_player.config.state import PlayerState, load_state
from auracast_player.sendspin.player import SendspinPlayer

if TYPE_CHECKING:
    from pathlib import Path


CLIENT_ID = Identity.generate().peer_id


class NullSink:
    """A broadcast stand-in that discards everything."""

    queued_seconds = 0.0

    async def send_pcm(self, pcm: bytes) -> None:
        """Discard a frame."""

    async def send_silence(self) -> None:
        """Discard a silent frame."""


def create_player(
    state_dir: Path, *, allow_unpaired: bool = False
) -> tuple[SendspinPlayer, PlayerState, Transmitter]:
    """Build a player that has not been started."""
    options = parse_options(
        {"auracast_controller": "/dev/test", "name": "Kitchen", "allow_unpaired": allow_unpaired}
    )
    state = PlayerState()
    transmitter = Transmitter(NullSink(), state)
    return SendspinPlayer(options, state, state_dir, transmitter), state, transmitter


def command(**fields: object) -> ServerCommandPayload:
    """Build a server command for the player role."""
    return ServerCommandPayload(player=PlayerCommandPayload(**fields))  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_volume_and_mute_commands_update_and_save_the_state(tmp_path: Path) -> None:
    """Apply the server's volume and mute, and keep them across a restart."""
    player, state, _ = create_player(tmp_path)

    player._on_server_command(command(command=PlayerCommand.VOLUME, volume=35))
    player._on_server_command(command(command=PlayerCommand.MUTE, mute=True))

    assert (state.volume, state.muted) == (35, True)
    saved = load_state(tmp_path)
    assert (saved.volume, saved.muted) == (35, True)


@pytest.mark.asyncio
async def test_other_commands_change_nothing(tmp_path: Path) -> None:
    """Ignore commands the player does not handle."""
    player, state, _ = create_player(tmp_path)
    before = (state.volume, state.muted)

    player._on_server_command(ServerCommandPayload())
    player._on_server_command(command(command=PlayerCommand.SET_OUTPUT_DELAY, output_delay_ms=50))

    assert (state.volume, state.muted) == before


def test_audio_chunks_are_queued_and_cleared_for_the_player_role(tmp_path: Path) -> None:
    """Queue received audio, and drop it when the stream ends or is cleared."""
    player, _, transmitter = create_player(tmp_path)

    player._on_audio_chunk(0, bytes(FRAME_BYTES), None, 0)  # type: ignore[arg-type]
    assert transmitter.buffered_bytes == FRAME_BYTES

    player._on_stream_dropped(["artwork"])
    assert transmitter.buffered_bytes == FRAME_BYTES

    player._on_stream_dropped(["player@v1"])
    assert transmitter.buffered_bytes == 0

    player._on_audio_chunk(0, bytes(FRAME_BYTES), None, 0)  # type: ignore[arg-type]
    player._on_stream_dropped(["player"])
    assert transmitter.buffered_bytes == 0

    player._on_audio_chunk(0, bytes(FRAME_BYTES), None, 0)  # type: ignore[arg-type]
    player._on_stream_dropped(None)
    assert transmitter.buffered_bytes == 0


def test_a_server_set_output_delay_is_saved(tmp_path: Path) -> None:
    """Keep a delay the server set, so the next start begins with it."""
    player, state, _ = create_player(tmp_path)

    player._on_output_delay(80.0)

    assert state.output_delay_ms == 80.0
    assert load_state(tmp_path).output_delay_ms == 80.0


class FakeClient:
    """A Sendspin client stand-in that records how it was disconnected."""

    def __init__(self) -> None:
        """Start with no disconnect recorded."""
        self.reasons: list[GoodbyeReason] = []

    async def disconnect(self, reason: GoodbyeReason) -> None:
        """Record the goodbye reason."""
        self.reasons.append(reason)


class FakeListener:
    """A listener stand-in that records that it was stopped."""

    def __init__(self) -> None:
        """Start not stopped."""
        self.stopped = False

    async def stop(self) -> None:
        """Record the stop."""
        self.stopped = True


@pytest.mark.asyncio
async def test_stop_says_restart_so_the_server_keeps_redialling(tmp_path: Path) -> None:
    """Disconnect with a restart goodbye, then stop the listener."""
    player, _, _ = create_player(tmp_path)
    client, listener = FakeClient(), FakeListener()
    player._client = client  # type: ignore[assignment]
    player._listener = listener  # type: ignore[assignment]

    await player.stop()

    assert client.reasons == [GoodbyeReason.RESTART]
    assert listener.stopped is True
