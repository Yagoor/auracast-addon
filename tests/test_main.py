"""Tests for the command line."""

from __future__ import annotations

from pathlib import Path

import pytest

from auracast_player.__main__ import parse_args
from auracast_player.config.options import DEFAULT_OPTIONS_FILE
from auracast_player.config.state import DEFAULT_STATE_DIR


def test_parse_args_defaults_to_the_add_on_paths() -> None:
    """Run with no arguments inside the add-on, where the Supervisor sets everything up."""
    args = parse_args([])

    assert args.options == DEFAULT_OPTIONS_FILE
    assert args.state_dir == DEFAULT_STATE_DIR


def test_parse_args_takes_paths_and_rejects_unknown_arguments() -> None:
    """Point the player at other files for a local run, and refuse a typo."""
    args = parse_args(["--options", "o.json", "--state-dir", "state"])

    assert args.options == Path("o.json")
    assert args.state_dir == Path("state")
    with pytest.raises(SystemExit):
        parse_args(["--optons", "o.json"])
