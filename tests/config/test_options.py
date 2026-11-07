"""Tests for the add-on options."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import pytest

from auracast_player.config.options import (
    OptionsError,
    load_options,
    parse_manufacturer_data,
    parse_options,
)

if TYPE_CHECKING:
    from pathlib import Path

CONTROLLER = "/dev/serial/by-id/usb-Zephyr_HCI_UART-if00"


def test_defaults_when_only_the_controller_is_set() -> None:
    """Fall back to the defaults for everything that was left empty."""
    options = parse_options({"auracast_controller": CONTROLLER, "name": "", "log_level": "info"})

    assert options.controller == CONTROLLER
    assert options.player_name == "Auracast"
    assert options.broadcast_name == "Auracast"
    assert options.baudrate == 1_000_000
    assert options.buffer_ms == 250
    assert options.allow_unpaired is False


def test_broadcast_name_defaults_to_the_player_name() -> None:
    """Use the player name for receivers too unless a broadcast name is set."""
    named = parse_options({"auracast_controller": CONTROLLER, "name": "Kitchen"})
    separate = parse_options(
        {"auracast_controller": CONTROLLER, "name": "Kitchen", "broadcast_name": "Kitchen Radio"}
    )

    assert named.broadcast_name == "Kitchen"
    assert separate.broadcast_name == "Kitchen Radio"


@pytest.mark.parametrize(
    ("raw", "message"),
    [
        ({}, "Select the Auracast controller"),
        ({"auracast_controller": "  "}, "Select the Auracast controller"),
        ({"auracast_controller": CONTROLLER, "baudrate": 5}, "baud rate"),
        ({"auracast_controller": CONTROLLER, "baudrate": "fast"}, "baud rate"),
        ({"auracast_controller": CONTROLLER, "baudrate": True}, "baud rate"),
        ({"auracast_controller": CONTROLLER, "buffer_ms": 10}, "audio buffer"),
        ({"auracast_controller": CONTROLLER, "buffer_ms": 5000}, "audio buffer"),
        ({"auracast_controller": CONTROLLER, "buffer_ms": "big"}, "audio buffer"),
        ({"auracast_controller": CONTROLLER, "name": "abc"}, "broadcast name"),
        ({"auracast_controller": CONTROLLER, "name": "x" * 33}, "broadcast name"),
        ({"auracast_controller": CONTROLLER, "log_level": "loud"}, "log level"),
    ],
)
def test_unusable_options_are_rejected(raw: dict[str, Any], message: str) -> None:
    """Name the option that cannot be used."""
    with pytest.raises(OptionsError, match=message):
        parse_options(raw)


def test_manufacturer_data_is_parsed() -> None:
    """Turn the manufacturer data option into company IDs and payloads."""
    options = parse_options(
        {"auracast_controller": CONTROLLER, "manufacturer_data": "0x0059:0102; 1234:abcd"}
    )

    assert options.manufacturer_data == {0x59: bytes([1, 2]), 1234: bytes([0xAB, 0xCD])}
    assert parse_options({"auracast_controller": CONTROLLER}).manufacturer_data is None


@pytest.mark.parametrize("value", ["59", "zz:0102", "0x10000:01", "59:xyz", "59:01;"])
def test_unusable_manufacturer_data_is_rejected(value: str) -> None:
    """Name the manufacturer data when it cannot be used."""
    with pytest.raises(OptionsError, match="manufacturer data"):
        parse_options({"auracast_controller": CONTROLLER, "manufacturer_data": value})


def test_load_options_reads_the_supervisor_file(tmp_path: Path) -> None:
    """Read the options file the Supervisor writes."""
    path = tmp_path / "options.json"
    path.write_text(json.dumps({"auracast_controller": CONTROLLER, "allow_unpaired": True}))

    assert load_options(path).allow_unpaired is True


@pytest.mark.parametrize("content", [None, "not json", "[]"])
def test_load_options_rejects_a_missing_or_malformed_file(
    tmp_path: Path, content: str | None
) -> None:
    """Report a file that cannot be used as an option error."""
    path = tmp_path / "options.json"
    if content is not None:
        path.write_text(content)

    with pytest.raises(OptionsError):
        load_options(path)


def test_manufacturer_data_parses_decimal_and_hex_company_ids() -> None:
    """Parse the reference format, including multiple optional entries."""
    assert parse_manufacturer_data(None) is None
    assert parse_manufacturer_data("") is None
    assert parse_manufacturer_data("1234:abcd;0x59:0102") == {
        1234: bytes.fromhex("abcd"),
        0x59: bytes.fromhex("0102"),
    }


@pytest.mark.parametrize(
    ("value", "error"),
    [
        ("not-a-company:abcd", "Invalid manufacturer company ID"),
        ("65536:abcd", "company ID must be between"),
        ("87:xyz", "valid hexadecimal data"),
        ("87:abc", "valid hexadecimal data"),
        ("87:", "COMPANY_ID:HEX_DATA"),
        ("87:01;", "empty entry"),
    ],
)
def test_manufacturer_data_rejects_invalid_entries(value: str, error: str) -> None:
    """Reject invalid company identifiers and payloads with a useful error."""
    with pytest.raises(ValueError, match=error):
        parse_manufacturer_data(value)
