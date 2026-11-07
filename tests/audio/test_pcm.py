"""Tests for the PCM helpers."""

from __future__ import annotations

import struct

from auracast_player.audio.pcm import FRAME_BYTES, FrameBuffer, apply_gain, volume_gain


def samples(*values: int) -> bytes:
    """Pack 16-bit little-endian samples."""
    return struct.pack(f"<{len(values)}h", *values)


def test_a_frame_is_ten_milliseconds_of_48khz_stereo() -> None:
    """Match the LC3 frame the broadcast sends."""
    assert FRAME_BYTES == 480 * 2 * 2


def test_volume_follows_the_sendspin_curve() -> None:
    """Map volume to the perceived-loudness gain the protocol asks for."""
    assert volume_gain(100, muted=False) == 1.0
    assert volume_gain(0, muted=False) == 0.0
    assert volume_gain(50, muted=False) == 0.5**1.5
    assert volume_gain(80, muted=True) == 0.0


def test_gain_scales_samples() -> None:
    """Scale samples, and leave full volume untouched."""
    pcm = samples(1000, -1000, 32767, -32768)

    assert apply_gain(pcm, 1.0) is pcm
    assert apply_gain(pcm, 0.5) == samples(500, -500, 16384, -16384)
    assert apply_gain(pcm, 0.0) == bytes(len(pcm))


def test_the_buffer_hands_out_whole_frames_only() -> None:
    """Hold back a partial frame until the rest arrives."""
    buffer = FrameBuffer(FRAME_BYTES * 10)
    buffer.add(bytes(FRAME_BYTES - 4))

    assert buffer.pop_frame() is None

    buffer.add(bytes(8))
    assert buffer.pop_frame() == bytes(FRAME_BYTES)
    assert len(buffer) == 4


def test_the_buffer_drops_the_oldest_audio_beyond_its_capacity() -> None:
    """Keep the newest audio and the channels aligned."""
    buffer = FrameBuffer(FRAME_BYTES)
    buffer.add(bytes([1]) * FRAME_BYTES)
    buffer.add(bytes([2]) * 8)

    assert len(buffer) == FRAME_BYTES
    assert buffer.dropped_bytes == 8
    frame = buffer.pop_frame()
    assert frame is not None
    assert frame.endswith(bytes([2]) * 8)


def test_clear_empties_the_buffer() -> None:
    """Drop everything on a seek."""
    buffer = FrameBuffer(FRAME_BYTES * 2)
    buffer.add(bytes(FRAME_BYTES))
    buffer.clear()

    assert buffer.pop_frame() is None
