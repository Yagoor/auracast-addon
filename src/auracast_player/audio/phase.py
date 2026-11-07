"""The phases a stream goes through on its way to the broadcast, as a finite state machine."""

from __future__ import annotations

import logging

from statemachine import State, StateMachine

LOGGER = logging.getLogger(__name__)


class Phase(StateMachine):
    """What the transmitter is doing with the broadcast, and the events that change it.

    ``idle``
        No stream. Silence is sent, which keeps the broadcast alive between streams.
    ``buffering``
        A stream is waiting for its prebuffer, or its audio ran dry. Nothing is sent, so
        receivers conceal the gap instead of decoding a frame of silence, which is heard as a
        click.
    ``playing``
        Audio is going out.

    An event that does not apply in the current phase does nothing, so callers can raise
    ``begin`` for every chunk of audio and ``reset`` whenever a stream ends.
    """

    allow_event_without_transition = True

    idle = State(initial=True)
    buffering = State()
    playing = State()

    begin = idle.to(buffering)
    ready = buffering.to(playing)
    starve = playing.to(buffering)
    reset = buffering.to(idle) | playing.to(idle)

    def __init__(self) -> None:
        """Start idle, with no underruns counted."""
        self.underruns = 0
        super().__init__()

    def after_transition(self, event: str, source: State, target: State) -> None:
        """Log every change of phase, for following a stream at debug level."""
        LOGGER.debug("Phase %s -> %s (%s)", source.id, target.id, event)

    def on_starve(self) -> None:
        """Count an underrun and say so."""
        self.underruns += 1
        LOGGER.warning(
            "Audio underrun %d: the server did not deliver audio fast enough, "
            "buffering again before resuming",
            self.underruns,
        )
