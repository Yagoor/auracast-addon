"""Tests for the logging setup."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pytest

from auracast_player.logs import configure_logging

if TYPE_CHECKING:
    from collections.abc import Iterator


@pytest.fixture(autouse=True)
def restore_logging() -> Iterator[None]:
    """Put the logging configuration back after each test."""
    root = logging.getLogger()
    handlers, level = list(root.handlers), root.level
    package_level = logging.getLogger("auracast_player").level
    yield
    root.handlers[:] = handlers
    root.setLevel(level)
    logging.getLogger("auracast_player").setLevel(package_level)


def test_debug_applies_to_the_player_and_not_to_its_libraries() -> None:
    """Show the player's debug messages without the libraries' packet traces."""
    configure_logging("debug")

    assert logging.getLogger("auracast_player.audio.transmitter").isEnabledFor(logging.DEBUG)
    assert not logging.getLogger("bumble.host").isEnabledFor(logging.DEBUG)
    assert not logging.getLogger("serialx.descriptor_transport").isEnabledFor(logging.DEBUG)
    assert logging.getLogger("bumble.host").isEnabledFor(logging.INFO)


def test_libraries_follow_a_stricter_level() -> None:
    """Quieten the libraries too when the add-on asks for warnings only."""
    configure_logging("warning")

    assert not logging.getLogger("aiosendspin.client.listener").isEnabledFor(logging.INFO)
    assert not logging.getLogger("auracast_player.sendspin.player").isEnabledFor(logging.INFO)
    assert logging.getLogger("auracast_player.sendspin.player").isEnabledFor(logging.WARNING)


def test_an_unknown_level_falls_back_to_info() -> None:
    """Never fail to start because of a log level."""
    configure_logging("chatty")

    assert logging.getLogger("auracast_player").isEnabledFor(logging.INFO)
    assert not logging.getLogger("auracast_player").isEnabledFor(logging.DEBUG)
