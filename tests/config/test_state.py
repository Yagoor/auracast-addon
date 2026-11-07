"""Tests for the state kept across restarts."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from auracast_player.config.state import (
    PlayerState,
    generate_device_address,
    load_identity,
    load_state,
    parse_device_address,
    save_state,
)

if TYPE_CHECKING:
    from pathlib import Path


def test_state_survives_a_restart(tmp_path: Path) -> None:
    """Keep the address and broadcast ID, so receivers recognise the broadcast."""
    first = load_state(tmp_path)
    first.volume = 42
    first.muted = True
    first.output_delay_ms = 12.5
    save_state(tmp_path, first)

    second = load_state(tmp_path)

    assert second == first


def test_a_new_state_has_a_static_address_and_a_valid_broadcast_id(tmp_path: Path) -> None:
    """Generate usable values on first start."""
    state = load_state(tmp_path)

    assert parse_device_address(state.device_address) == state.device_address
    assert 0 < state.broadcast_id < 0x1000000
    assert (tmp_path / "state.json").exists() is False


@pytest.mark.parametrize(
    "stored",
    [
        {"device_address": "00:11:22:33:44:55", "broadcast_id": 0, "volume": "loud", "muted": 1},
        {"device_address": 5, "broadcast_id": 2**30, "volume": True, "output_delay_ms": -3},
        {"device_address": None, "broadcast_id": "1", "output_delay_ms": "x"},
    ],
)
def test_malformed_values_are_replaced(tmp_path: Path, stored: dict[str, object]) -> None:
    """Replace anything missing or malformed instead of failing to start."""
    (tmp_path / "state.json").write_text(json.dumps(stored))

    state = load_state(tmp_path)

    assert 0 < state.broadcast_id < 0x1000000
    assert state.volume == 100
    assert state.muted is False
    assert state.output_delay_ms == 0.0


def test_a_corrupt_state_file_is_ignored(tmp_path: Path) -> None:
    """Start from fresh values when the file cannot be read."""
    (tmp_path / "state.json").write_text("{not json")

    assert isinstance(load_state(tmp_path), PlayerState)


def test_volume_is_kept_within_range(tmp_path: Path) -> None:
    """Clamp a stored volume."""
    (tmp_path / "state.json").write_text(json.dumps({"volume": 250}))

    assert load_state(tmp_path).volume == 100


def test_the_identity_is_created_once_and_kept_private(tmp_path: Path) -> None:
    """Reuse the same Sendspin identity across restarts, readable only by its owner."""
    first = load_identity(tmp_path)
    second = load_identity(tmp_path)

    assert first.peer_id == second.peer_id
    assert (tmp_path / "identity.key").stat().st_mode & 0o077 == 0


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("F0:F1:F2:F3:F4:F5", "F0:F1:F2:F3:F4:F5"),
        ("f0:f1:f2:f3:f4:f5", "F0:F1:F2:F3:F4:F5"),
        ("00:11:22:33:44:55", None),
        ("nonsense", None),
        (None, None),
        (100, None),
    ],
)
def test_parse_device_address_only_accepts_static_addresses(
    value: object, expected: str | None
) -> None:
    """Accept a stored static address and reject anything else."""
    assert parse_device_address(value) == expected


def test_generated_device_address_is_a_valid_static_address() -> None:
    """Generate addresses that pass the check applied to stored values."""
    address = generate_device_address()

    assert parse_device_address(address) == address
