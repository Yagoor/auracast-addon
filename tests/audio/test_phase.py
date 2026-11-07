"""Tests for the transmitter's phase state machine."""

from __future__ import annotations

import logging

import pytest

from auracast_player.audio.phase import Phase


def test_a_stream_goes_from_idle_through_buffering_to_playing() -> None:
    """Follow a stream from its first audio to playing."""
    phase = Phase()
    assert phase.idle.is_active

    phase.begin()
    assert phase.buffering.is_active

    phase.ready()
    assert phase.playing.is_active


def test_running_dry_goes_back_to_buffering_and_counts_an_underrun(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Count each underrun, and warn about it."""
    phase = Phase()
    phase.begin()
    phase.ready()

    with caplog.at_level(logging.WARNING, logger="auracast_player.audio.phase"):
        phase.starve()

    assert phase.buffering.is_active
    assert phase.underruns == 1
    assert any("Audio underrun 1" in record.getMessage() for record in caplog.records)


@pytest.mark.parametrize("steps", [(), ("begin",), ("begin", "ready")])
def test_reset_returns_to_idle_from_any_phase(steps: tuple[str, ...]) -> None:
    """End a stream wherever it is."""
    phase = Phase()
    for step in steps:
        getattr(phase, step)()

    phase.reset()

    assert phase.idle.is_active


def test_events_that_do_not_apply_do_nothing() -> None:
    """Let callers raise events without checking the phase first."""
    phase = Phase()

    phase.ready()
    phase.starve()
    phase.reset()
    assert phase.idle.is_active
    assert phase.underruns == 0

    phase.begin()
    phase.begin()
    phase.starve()
    assert phase.buffering.is_active
    assert phase.underruns == 0

    phase.ready()
    phase.ready()
    phase.begin()
    assert phase.playing.is_active


def test_every_transition_is_logged_at_debug(caplog: pytest.LogCaptureFixture) -> None:
    """Make a stream's phases visible when debugging."""
    phase = Phase()

    with caplog.at_level(logging.DEBUG, logger="auracast_player.audio.phase"):
        phase.begin()
        phase.ready()
        phase.starve()
        phase.reset()

    messages = [record.getMessage() for record in caplog.records if record.levelno == logging.DEBUG]
    assert messages == [
        "Phase idle -> buffering (begin)",
        "Phase buffering -> playing (ready)",
        "Phase playing -> buffering (starve)",
        "Phase buffering -> idle (reset)",
    ]
