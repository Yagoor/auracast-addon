"""Tests for the advertising data of the broadcast."""

from __future__ import annotations

from auracast_player.auracast.advertising import build_advertising_data, build_periodic_data


def test_advertising_data_carries_the_name_and_manufacturer_data() -> None:
    """Advertise the broadcast name, and each manufacturer payload as its own structure."""
    data = build_advertising_data("Kitchen", 0x123456, {0x59: bytes([1, 2])})

    assert bytes([8, 0x09]) + b"Kitchen" in data  # complete local name
    assert bytes([8, 0x30]) + b"Kitchen" in data  # broadcast name
    assert bytes([5, 0xFF, 0x59, 0x00, 1, 2]) in data  # manufacturer specific data


def test_advertising_data_without_manufacturer_data_has_no_such_structure() -> None:
    """Add nothing when no manufacturer data is set."""
    assert b"\xff\x59\x00" not in build_advertising_data("Kitchen", 1, None)


def test_periodic_data_describes_one_bis_per_channel() -> None:
    """Announce the LC3 setup, with the presentation delay and the frame size."""
    stereo = build_periodic_data(40_000, 100, 2)
    mono = build_periodic_data(40_000, 100, 1)

    assert (40_000).to_bytes(3, "little") in stereo
    assert len(stereo) > len(mono)
