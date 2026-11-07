"""Raw PCM helpers: framing and software volume for 16-bit little-endian stereo."""

from __future__ import annotations

from array import array
from typing import Final

from ..constants import BIT_DEPTH, CHANNELS, FRAME_DURATION_MS, SAMPLE_RATE

BYTES_PER_SAMPLE_FRAME: Final = CHANNELS * BIT_DEPTH // 8
FRAME_BYTES: Final = SAMPLE_RATE * FRAME_DURATION_MS // 1000 * BYTES_PER_SAMPLE_FRAME


def volume_gain(volume: int, *, muted: bool) -> float:
    """
    Return the linear gain for a Sendspin volume.

    Sendspin volume is perceived loudness, which maps to a gain of ``(volume / 100) ** 1.5``.

    :param volume: Volume from 0 to 100.
    :param muted: Whether the player is muted, which silences it whatever the volume.
    """
    if muted or volume <= 0:
        return 0.0
    return float((min(volume, 100) / 100) ** 1.5)


def apply_gain(pcm: bytes, gain: float) -> bytes:
    """
    Scale 16-bit little-endian PCM.

    :param pcm: Interleaved samples.
    :param gain: Linear gain, where 1.0 leaves the audio unchanged.
    """
    if gain >= 1.0:
        return pcm
    if gain <= 0.0:
        return bytes(len(pcm))
    samples = array("h")
    samples.frombytes(pcm)
    scaled = array("h", (round(sample * gain) for sample in samples))
    return scaled.tobytes()


class FrameBuffer:
    """Collect PCM and hand it out in whole LC3-sized frames."""

    def __init__(self, capacity_bytes: int) -> None:
        """
        Create an empty buffer.

        :param capacity_bytes: The most audio kept; the oldest is dropped beyond it.
        """
        self._data = bytearray()
        self._capacity = capacity_bytes
        self.dropped_bytes = 0

    def __len__(self) -> int:
        """Return the number of buffered bytes."""
        return len(self._data)

    def add(self, pcm: bytes) -> None:
        """
        Append audio.

        :param pcm: Interleaved samples.
        """
        self._data.extend(pcm)
        excess = len(self._data) - self._capacity
        if excess > 0:
            # Whole sample frames only, so the channels stay aligned
            excess += -excess % BYTES_PER_SAMPLE_FRAME
            del self._data[:excess]
            self.dropped_bytes += excess

    def pop_frame(self) -> bytes | None:
        """Return the next whole frame, or ``None`` when there is not one yet."""
        if len(self._data) < FRAME_BYTES:
            return None
        frame = bytes(self._data[:FRAME_BYTES])
        del self._data[:FRAME_BYTES]
        return frame

    def clear(self) -> None:
        """Drop everything buffered."""
        self._data.clear()
