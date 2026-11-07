"""Bumble and LC3 implementation for an Auracast broadcast."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import serialx
from bumble import core, device, hci
from lc3 import BaseError as LC3Error
from lc3 import Encoder

from .advertising import build_advertising_data, build_periodic_data
from .controller import ControllerInfo, find_missing_auracast_support
from .serial_hci import open_hci_transport

if TYPE_CHECKING:
    from collections.abc import Awaitable

LOGGER = logging.getLogger(__name__)
LC3_BITRATE = 160_000
TEARDOWN_STEP_TIMEOUT = 2.0
# Errors raised by Bumble, the serial transport (serialx and OSError, including timeouts) and liblc3
BROADCAST_ERRORS = (core.BaseBumbleError, LC3Error, OSError, serialx.SerialException)


@dataclass(frozen=True, slots=True)
class BroadcastConfig:
    """Settings used to create the Bluetooth LE Audio broadcast."""

    name: str
    serial_port: str
    baudrate: int
    manufacturer_data: dict[int, bytes] | None = None
    broadcast_id: int = 0
    device_address: str | None = None
    sample_rate: int = 48_000
    frame_duration_us: int = 10_000
    channels: int = 2
    presentation_delay_us: int = 40_000
    max_transport_latency_ms: int = 65


class AuracastBroadcaster:
    """Create a Bumble BIG and submit interleaved PCM as LC3 ISO packets."""

    def __init__(self, config: BroadcastConfig) -> None:
        """Initialize the broadcaster with its settings."""
        self.config = config
        self._device: device.Device | None = None
        self.controller: ControllerInfo | None = None
        self._transport: Any = None
        self._advertising_set: device.AdvertisingSet | None = None
        self._big: device.Big | None = None
        self._streams: list[device.IsoPacketStream] = []
        self._encoder: Encoder | None = None
        self._frame_bytes = 0
        self._bytes_per_bis = 0
        self._samples_per_frame = 0
        self._pcm_buffer = bytearray()
        self._encoded_silence: bytes | None = None

    @property
    def running(self) -> bool:
        """Return whether the broadcast BIG is active."""
        return self._big is not None

    async def start(self) -> None:
        """Open the UART controller and start the Auracast broadcast."""
        if self.running:
            return

        config = self.config
        self._encoder = Encoder(
            frame_duration_us=config.frame_duration_us,
            sample_rate_hz=config.sample_rate,
            num_channels=config.channels,
        )
        self._frame_bytes = self._encoder.get_frame_bytes(LC3_BITRATE)
        self._bytes_per_bis = self._frame_bytes // config.channels
        self._samples_per_frame = config.sample_rate * config.frame_duration_us // 1_000_000
        self._pcm_buffer.clear()
        self._encoded_silence = self._encode_silence()

        started = False
        try:
            LOGGER.debug(
                "Starting Auracast broadcast %r over %s at %d baud: LC3 bitrate=%d, "
                "sample_rate=%d, channels=%d, broadcast_id=0x%06X",
                config.name,
                config.serial_port,
                config.baudrate,
                LC3_BITRATE,
                config.sample_rate,
                config.channels,
                config.broadcast_id,
            )
            self._transport = await open_hci_transport(config.serial_port, config.baudrate)
            LOGGER.debug("Opened Auracast HCI transport: %s", config.serial_port)
            hci_source, hci_sink = self._transport
            self._device = device.Device.from_config_with_hci(
                device.DeviceConfiguration(
                    name=config.name,
                    address=hci.Address(config.device_address)
                    if config.device_address
                    else hci.Address.generate_static_address(),
                ),
                hci_source,
                hci_sink,
            )
            LOGGER.debug("Powering on Bumble host and Bluetooth controller")
            await self._device.power_on()
            LOGGER.debug(
                "Bumble host initialized: controller HCI version=%s, "
                "supported_commands=0x%X, LE_features=%s",
                self._device.host.local_version,
                self._device.host.local_supported_commands,
                self._device.host.local_le_features,
            )
            await self._read_controller_stack()
            self._validate_controller()
            await self._create_broadcast()
            started = True
        finally:
            if not started:
                await self.stop()

    @property
    def queued_seconds(self) -> float:
        """Return the duration of audio submitted but not yet transmitted."""
        if not self._streams:
            return 0.0
        pending_sdus = self._streams[0].data_packet_queue.pending
        return pending_sdus / len(self._streams) * self.config.frame_duration_us / 1_000_000

    async def send_pcm(self, pcm: bytes) -> None:
        """
        Encode complete PCM frames and submit one SDU per BIS.

        :param pcm: Interleaved 16-bit little-endian PCM; a trailing partial frame is buffered.
        """
        if not self.running or self._encoder is None:
            return
        self._pcm_buffer.extend(pcm)
        bytes_per_pcm_frame = self._samples_per_frame * self.config.channels * 2
        while len(self._pcm_buffer) >= bytes_per_pcm_frame:
            pcm_frame = bytes(self._pcm_buffer[:bytes_per_pcm_frame])
            del self._pcm_buffer[:bytes_per_pcm_frame]
            await self._submit_frame(pcm_frame)

    async def send_silence(self) -> None:
        """Submit a cached encoded silence frame to every BIS."""
        if not self.running or self._encoded_silence is None:
            return
        await self._submit_encoded_frame(self._encoded_silence)

    async def stop(self) -> None:
        """Stop the BIG and close the controller transport."""
        big, self._big = self._big, None
        if big:
            await _teardown_step(big.terminate(), "terminating the Auracast BIG")

        advertising_set, self._advertising_set = self._advertising_set, None
        if advertising_set:
            await _teardown_step(advertising_set.stop(), "stopping Auracast advertising")

        current_device, self._device = self._device, None
        if current_device:
            await _teardown_step(current_device.power_off(), "powering off the controller")

        current_transport, self._transport = self._transport, None
        if current_transport:
            await _teardown_step(current_transport.close(), "closing the controller transport")
        self._streams.clear()
        self._encoder = None
        self._pcm_buffer.clear()
        self._encoded_silence = None

    def _encode_silence(self) -> bytes:
        """Encode a silent frame with an encoder that has never seen music."""
        config = self.config
        silence_encoder = Encoder(
            frame_duration_us=config.frame_duration_us,
            sample_rate_hz=config.sample_rate,
            num_channels=config.channels,
        )
        encoded: bytes = silence_encoder.encode(
            bytes(self._samples_per_frame * config.channels * 2),
            num_bytes=self._frame_bytes,
            bit_depth=16,
        )
        return encoded

    async def _submit_frame(self, pcm_frame: bytes) -> None:
        """Encode one PCM frame with LC3 and write each channel to its BIS."""
        assert self._encoder is not None
        encoded = self._encoder.encode(pcm_frame, num_bytes=self._frame_bytes, bit_depth=16)
        await self._submit_encoded_frame(encoded)

    async def _submit_encoded_frame(self, encoded: bytes) -> None:
        """Write one already encoded LC3 frame to each BIS."""
        await asyncio.gather(
            *(
                stream.write(
                    encoded[index * self._bytes_per_bis : (index + 1) * self._bytes_per_bis]
                )
                for index, stream in enumerate(self._streams)
            )
        )

    def _validate_controller(self) -> None:
        """Raise when the controller cannot transmit an Auracast broadcast."""
        assert self._device is not None
        if missing := find_missing_auracast_support(self._device):
            raise core.NotSupportedError(
                f"The Bluetooth controller does not support Auracast broadcasting: "
                f"missing {', '.join(missing)}"
            )

    async def _read_controller_stack(self) -> None:
        """Read the Bluetooth controller's HCI version, vendor, and revisions."""
        if self._device is None:
            return
        parameters = self._device.host.local_version
        if parameters is None:
            supports_read_version = self._device.host.supports_command(
                hci.HCI_READ_LOCAL_VERSION_INFORMATION_COMMAND
            )
            LOGGER.debug(
                "Controller local HCI version information is unavailable "
                "(read-version command supported=%s, supported-command-bitmap=0x%X)",
                supports_read_version,
                self._device.host.local_supported_commands,
            )
            return
        self.controller = ControllerInfo.from_local_version(parameters)
        LOGGER.debug("Detected Auracast controller stack: %s", self.controller.stack)

    async def _create_broadcast(self) -> None:
        """Configure public broadcast announcements and create the BIG."""
        assert self._device is not None
        config = self.config
        self._advertising_set = await self._device.create_advertising_set(
            advertising_parameters=device.AdvertisingParameters(
                advertising_event_properties=device.AdvertisingEventProperties(
                    is_connectable=False
                ),
                primary_advertising_interval_min=60,
                primary_advertising_interval_max=60,
                advertising_sid=0,
            ),
            advertising_data=build_advertising_data(
                config.name, config.broadcast_id, config.manufacturer_data
            ),
            periodic_advertising_parameters=device.PeriodicAdvertisingParameters(
                periodic_advertising_interval_min=60,
                periodic_advertising_interval_max=60,
            ),
            periodic_advertising_data=build_periodic_data(
                config.presentation_delay_us, self._bytes_per_bis, config.channels
            ),
            auto_restart=True,
            auto_start=True,
        )
        await self._advertising_set.start_periodic()
        self._big = await self._device.create_big(
            self._advertising_set,
            parameters=device.BigParameters(
                num_bis=config.channels,
                sdu_interval=config.frame_duration_us,
                max_sdu=self._bytes_per_bis,
                max_transport_latency=config.max_transport_latency_ms,
                rtn=4,
            ),
        )
        self._streams = []
        for link in self._big.bis_links:
            await link.setup_data_path(direction=link.Direction.HOST_TO_CONTROLLER)
            self._streams.append(device.IsoPacketStream(link, 64))
        LOGGER.debug(
            "Auracast BIG created: bis_count=%d, max_sdu_per_bis=%d, presentation_delay_us=%d",
            len(self._streams),
            self._bytes_per_bis,
            config.presentation_delay_us,
        )
        LOGGER.info("Broadcasting %s with %d BIS streams", config.name, len(self._streams))


async def _teardown_step(step: Awaitable[None], description: str) -> None:
    """
    Run one best-effort teardown step, logging a timeout or Bumble/serial failure.

    :param step: The awaitable to run.
    :param description: What the step does, used in log messages.
    """
    try:
        await asyncio.wait_for(step, timeout=TEARDOWN_STEP_TIMEOUT)
    except TimeoutError:
        LOGGER.warning("Timed out %s", description)
    except BROADCAST_ERRORS as err:
        LOGGER.warning("Failed %s: %s", description, err)
