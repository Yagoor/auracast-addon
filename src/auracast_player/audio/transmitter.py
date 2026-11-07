"""Feeds the Auracast broadcast at the radio's pace from whatever audio is available."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Protocol

from ..constants import DEFAULT_BUFFER_MS, FRAME_DURATION_MS
from .pcm import FRAME_BYTES, FrameBuffer, apply_gain, volume_gain
from .phase import Phase

if TYPE_CHECKING:
    from ..config.state import PlayerState

# The most audio kept waiting for the broadcast. The server never sends more than the buffer it
# was told about, so this only caps what a misbehaving server could queue.
BUFFER_BYTES = 1000 * FRAME_BYTES // FRAME_DURATION_MS
# How much audio is let into the controller's queue ahead of the radio. Everything beyond this
# stays in the buffer here, so an underrun can be told apart from audio merely waiting its turn.
QUEUE_TARGET_S = 0.08
FRAME_SECONDS = FRAME_DURATION_MS / 1000


class FrameSink(Protocol):
    """The broadcast the audio is submitted to."""

    @property
    def queued_seconds(self) -> float:
        """Return the duration of audio submitted but not yet transmitted."""

    async def send_pcm(self, pcm: bytes) -> None:
        """Encode and submit one frame of PCM."""

    async def send_silence(self) -> None:
        """Submit one frame of silence."""


class Transmitter:
    """Send buffered audio to the broadcast, and silence while there is no stream."""

    def __init__(
        self, sink: FrameSink, state: PlayerState, prebuffer_ms: int = DEFAULT_BUFFER_MS
    ) -> None:
        """
        Create a transmitter.

        :param sink: The broadcast to feed.
        :param state: The player state, read for volume and mute on every frame.
        :param prebuffer_ms: How much audio to collect before playing, and again after the audio
            runs dry. A larger value rides out a late chunk at the cost of a later start.
        """
        self._sink = sink
        self._state = state
        self._buffer = FrameBuffer(BUFFER_BYTES)
        self._prebuffer_bytes = prebuffer_ms * FRAME_BYTES // FRAME_DURATION_MS
        self.phase = Phase()

    @property
    def underruns(self) -> int:
        """Return how many times the audio ran dry in the middle of a stream."""
        return self.phase.underruns

    @property
    def buffered_bytes(self) -> int:
        """Return how much audio is waiting to be transmitted."""
        return len(self._buffer)

    def feed(self, pcm: bytes) -> None:
        """
        Queue audio for transmission.

        :param pcm: 48 kHz stereo 16-bit little-endian PCM.
        """
        self.phase.begin()
        self._buffer.add(pcm)

    def clear(self) -> None:
        """Drop queued audio and go idle, as a seek or the end of a stream asks."""
        self._buffer.clear()
        self.phase.reset()

    async def run(self) -> None:
        """
        Transmit until cancelled.

        Frames are handed to the broadcast at the pace it transmits them, keeping only a short
        queue ahead of the radio. While idle, silence is sent. When audio runs dry in the middle
        of a stream nothing is sent instead, so receivers conceal the gap rather than decode a
        frame of silence, which is heard as a click.
        """
        while True:
            if self._sink.queued_seconds >= QUEUE_TARGET_S:
                await asyncio.sleep(FRAME_SECONDS / 2)
                continue
            frame = self._next_frame()
            if frame is not None:
                gain = volume_gain(self._state.volume, muted=self._state.muted)
                await self._sink.send_pcm(apply_gain(frame, gain))
            elif self.phase.idle.is_active:
                await self._sink.send_silence()
            else:
                await asyncio.sleep(FRAME_SECONDS / 2)

    def _next_frame(self) -> bytes | None:
        """Return the next frame to play, or ``None`` when there is nothing to play yet."""
        phase = self.phase
        if phase.playing.is_active:
            frame = self._buffer.pop_frame()
            if frame is not None:
                return frame
            phase.starve()
        if phase.buffering.is_active and len(self._buffer) >= self._prebuffer_bytes:
            phase.ready()
            return self._buffer.pop_frame()
        return None
