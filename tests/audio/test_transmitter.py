"""Tests for the transmit loop."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time

import pytest

from auracast_player.audio.pcm import FRAME_BYTES
from auracast_player.audio.transmitter import Transmitter
from auracast_player.config.state import PlayerState


class RecordingSink:
    """A broadcast stand-in that records what it was sent."""

    def __init__(self) -> None:
        """Start with nothing sent."""
        self.pcm: list[bytes] = []
        self.silence = 0
        self.queued_override: float | None = None
        self._started = time.monotonic()

    @property
    def queued_seconds(self) -> float:
        """Report a queue that drains in real time, as the controller's does."""
        if self.queued_override is not None:
            return self.queued_override
        sent = (len(self.pcm) + self.silence) * 0.01
        return max(0.0, sent - (time.monotonic() - self._started))

    async def send_pcm(self, pcm: bytes) -> None:
        """Record a frame."""
        self.pcm.append(pcm)

    async def send_silence(self) -> None:
        """Record a silent frame."""
        self.silence += 1


async def run_for(transmitter: Transmitter, seconds: float) -> None:
    """Run the transmitter briefly, then stop it."""
    task = asyncio.create_task(transmitter.run())
    await asyncio.sleep(seconds)
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task


@pytest.mark.asyncio
async def test_silence_is_sent_while_nothing_is_queued() -> None:
    """Keep the broadcast alive between tracks."""
    sink = RecordingSink()

    await run_for(Transmitter(sink, PlayerState()), 0.06)

    assert sink.silence >= 2
    assert sink.pcm == []


@pytest.mark.asyncio
async def test_queued_audio_is_sent_in_whole_frames() -> None:
    """Send each complete frame, then fall back to silence."""
    sink = RecordingSink()
    transmitter = Transmitter(sink, PlayerState(), prebuffer_ms=10)
    transmitter.feed(bytes(FRAME_BYTES * 2 + 8))

    await run_for(transmitter, 0.04)

    assert len(sink.pcm) == 2
    assert transmitter.buffered_bytes == 8


@pytest.mark.asyncio
async def test_volume_and_mute_apply_to_each_frame() -> None:
    """Read the current volume and mute for every frame."""
    sink = RecordingSink()
    state = PlayerState(volume=100, muted=True)
    transmitter = Transmitter(sink, state, prebuffer_ms=10)
    transmitter.feed(bytes([1]) * FRAME_BYTES)

    await run_for(transmitter, 0.03)

    assert sink.pcm == [bytes(FRAME_BYTES)]


@pytest.mark.asyncio
async def test_clear_drops_queued_audio() -> None:
    """Drop what is queued on a seek or a stream end."""
    sink = RecordingSink()
    transmitter = Transmitter(sink, PlayerState(), prebuffer_ms=10)
    transmitter.feed(bytes(FRAME_BYTES * 3))
    transmitter.clear()

    await run_for(transmitter, 0.03)

    assert sink.pcm == []


@pytest.mark.asyncio
async def test_nothing_plays_until_the_prebuffer_is_full() -> None:
    """Hold the audio back until there is enough to ride out a late chunk."""
    sink = RecordingSink()
    transmitter = Transmitter(sink, PlayerState(), prebuffer_ms=50)
    transmitter.feed(bytes(FRAME_BYTES * 4))

    await run_for(transmitter, 0.03)
    assert sink.pcm == []
    assert transmitter.buffered_bytes == FRAME_BYTES * 4

    transmitter.feed(bytes(FRAME_BYTES))
    await run_for(transmitter, 0.3)
    assert len(sink.pcm) == 5


@pytest.mark.asyncio
async def test_an_underrun_is_counted_and_buffers_again(caplog: pytest.LogCaptureFixture) -> None:
    """Fall back to silence when the audio runs dry, and wait for the prebuffer to refill."""
    sink = RecordingSink()
    transmitter = Transmitter(sink, PlayerState(), prebuffer_ms=30)
    transmitter.feed(bytes(FRAME_BYTES * 3))

    with caplog.at_level(logging.WARNING, logger="auracast_player.audio.transmitter"):
        await run_for(transmitter, 0.08)
        assert len(sink.pcm) == 3
        assert transmitter.underruns == 1
        assert any("underrun" in record.getMessage() for record in caplog.records)

        transmitter.feed(bytes(FRAME_BYTES))
        await run_for(transmitter, 0.04)
        assert len(sink.pcm) == 3

        transmitter.feed(bytes(FRAME_BYTES * 2))
        await run_for(transmitter, 0.04)
        assert len(sink.pcm) == 6


@pytest.mark.asyncio
async def test_clear_makes_the_next_stream_prebuffer_again() -> None:
    """Start a new stream from an empty cushion, not from where the last one stopped."""
    sink = RecordingSink()
    transmitter = Transmitter(sink, PlayerState(), prebuffer_ms=20)
    transmitter.feed(bytes(FRAME_BYTES * 2))
    await run_for(transmitter, 0.04)
    sent = len(sink.pcm)

    transmitter.clear()
    transmitter.feed(bytes(FRAME_BYTES))
    await run_for(transmitter, 0.03)

    assert len(sink.pcm) == sent


@pytest.mark.asyncio
async def test_frames_are_held_back_while_the_broadcast_queue_is_full() -> None:
    """Keep the audio in our own buffer instead of pouring it into the controller."""
    sink = RecordingSink()
    sink.queued_override = 1.0
    transmitter = Transmitter(sink, PlayerState(), prebuffer_ms=10)
    transmitter.feed(bytes(FRAME_BYTES * 5))

    await run_for(transmitter, 0.05)
    assert sink.pcm == []
    assert sink.silence == 0
    assert transmitter.buffered_bytes == FRAME_BYTES * 5

    sink.queued_override = None
    await run_for(transmitter, 0.02)
    assert len(sink.pcm) >= 1


@pytest.mark.asyncio
async def test_a_gap_mid_stream_is_left_quiet_not_filled_with_silence() -> None:
    """Send nothing when the audio runs dry, so receivers conceal it instead of clicking."""
    sink = RecordingSink()
    transmitter = Transmitter(sink, PlayerState(), prebuffer_ms=20)
    transmitter.feed(bytes(FRAME_BYTES * 2))
    await run_for(transmitter, 0.03)
    silence_before = sink.silence

    await run_for(transmitter, 0.1)

    assert transmitter.underruns >= 1
    assert sink.silence == silence_before
    assert len(sink.pcm) == 2


def test_the_phase_follows_the_stream() -> None:
    """Move from idle to buffering when audio arrives, and back to idle when it is cleared."""
    transmitter = Transmitter(RecordingSink(), PlayerState(), prebuffer_ms=10)
    assert transmitter.phase.idle.is_active

    transmitter.feed(bytes(8))
    assert transmitter.phase.buffering.is_active

    transmitter.clear()
    assert transmitter.phase.idle.is_active


@pytest.mark.asyncio
async def test_silence_resumes_once_the_stream_is_cleared() -> None:
    """Return to the idle keepalive after a stream ends, even if it ended in a gap."""
    sink = RecordingSink()
    transmitter = Transmitter(sink, PlayerState(), prebuffer_ms=10)
    transmitter.feed(bytes(FRAME_BYTES))
    await run_for(transmitter, 0.03)
    assert transmitter.phase.buffering.is_active
    silence_in_gap = sink.silence

    transmitter.clear()
    await run_for(transmitter, 0.03)

    assert silence_in_gap == 0
    assert sink.silence > 0


@pytest.mark.asyncio
async def test_playing_resumes_after_an_underrun_once_refilled() -> None:
    """Go back to playing when the prebuffer is full again."""
    sink = RecordingSink()
    transmitter = Transmitter(sink, PlayerState(), prebuffer_ms=20)
    transmitter.feed(bytes(FRAME_BYTES * 2))
    await run_for(transmitter, 0.04)
    assert transmitter.phase.buffering.is_active

    transmitter.feed(bytes(FRAME_BYTES * 2))
    await run_for(transmitter, 0.04)

    assert transmitter.phase.playing.is_active or transmitter.buffered_bytes == 0
    assert len(sink.pcm) == 4
