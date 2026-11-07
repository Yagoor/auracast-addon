"""The add-on options, as the Supervisor writes them to ``/data/options.json``."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ..constants import (
    DEFAULT_BAUDRATE,
    DEFAULT_BUFFER_MS,
    DEFAULT_PLAYER_NAME,
    MAX_BAUDRATE,
    MAX_BROADCAST_NAME_BYTES,
    MAX_BUFFER_MS,
    MIN_BAUDRATE,
    MIN_BROADCAST_NAME_BYTES,
    MIN_BUFFER_MS,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

DEFAULT_OPTIONS_FILE = Path("/data/options.json")
LOG_LEVELS = ("debug", "info", "warning", "error")


class OptionsError(ValueError):
    """The add-on options cannot be used."""


@dataclass(frozen=True, slots=True)
class Options:
    """Validated add-on options."""

    player_name: str
    broadcast_name: str
    controller: str
    baudrate: int
    buffer_ms: int
    log_level: str
    allow_unpaired: bool
    manufacturer_data: dict[int, bytes] | None


def load_options(path: Path = DEFAULT_OPTIONS_FILE) -> Options:
    """
    Read and validate the add-on options file.

    Raises ``OptionsError`` when the file is missing or holds unusable values.

    :param path: The options file written by the Supervisor.
    """
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as err:
        raise OptionsError(f"Cannot read the add-on options from {path}: {err}") from err
    if not isinstance(raw, dict):
        raise OptionsError(f"The add-on options in {path} are not an object")
    return parse_options(raw)


def parse_options(raw: Mapping[str, Any]) -> Options:
    """
    Validate raw option values.

    Raises ``OptionsError`` naming the first option that cannot be used.

    :param raw: The decoded options object.
    """
    player_name = _text(raw.get("name")) or DEFAULT_PLAYER_NAME
    broadcast_name = _text(raw.get("broadcast_name")) or player_name
    if not MIN_BROADCAST_NAME_BYTES <= len(broadcast_name.encode()) <= MAX_BROADCAST_NAME_BYTES:
        raise OptionsError(
            f"The broadcast name must be {MIN_BROADCAST_NAME_BYTES} to "
            f"{MAX_BROADCAST_NAME_BYTES} bytes long, {broadcast_name!r} is not"
        )
    controller = _text(raw.get("auracast_controller"))
    if not controller:
        raise OptionsError("Select the Auracast controller in the add-on configuration")
    baudrate = raw.get("baudrate", DEFAULT_BAUDRATE)
    if baudrate is None:
        baudrate = DEFAULT_BAUDRATE
    if (
        not isinstance(baudrate, int)
        or isinstance(baudrate, bool)
        or not MIN_BAUDRATE <= baudrate <= MAX_BAUDRATE
    ):
        raise OptionsError(
            f"The baud rate must be a number from {MIN_BAUDRATE} to {MAX_BAUDRATE}, "
            f"not {baudrate!r}"
        )
    buffer_ms = raw.get("buffer_ms")
    if buffer_ms is None:
        buffer_ms = DEFAULT_BUFFER_MS
    if (
        not isinstance(buffer_ms, int)
        or isinstance(buffer_ms, bool)
        or not MIN_BUFFER_MS <= buffer_ms <= MAX_BUFFER_MS
    ):
        raise OptionsError(
            f"The audio buffer must be a number from {MIN_BUFFER_MS} to {MAX_BUFFER_MS} "
            f"milliseconds, not {buffer_ms!r}"
        )
    try:
        manufacturer_data = parse_manufacturer_data(_text(raw.get("manufacturer_data")))
    except ValueError as err:
        raise OptionsError(f"The manufacturer data cannot be used: {err}") from err
    log_level = _text(raw.get("log_level")) or "info"
    if log_level not in LOG_LEVELS:
        raise OptionsError(f"The log level must be one of {', '.join(LOG_LEVELS)}")
    return Options(
        player_name=player_name,
        broadcast_name=broadcast_name,
        controller=controller,
        baudrate=baudrate,
        buffer_ms=buffer_ms,
        log_level=log_level,
        allow_unpaired=raw.get("allow_unpaired") is True,
        manufacturer_data=manufacturer_data,
    )


def _text(value: object) -> str:
    """Return a stripped option string, or an empty string when it is unset."""
    return value.strip() if isinstance(value, str) else ""


def parse_manufacturer_data(value: str | None) -> dict[int, bytes] | None:
    """
    Parse semicolon-separated company IDs and hexadecimal payloads.

    :param value: Entries in ``COMPANY_ID:HEX_DATA`` format, separated by semicolons.
    """
    if not value or not value.strip():
        return None

    entries: dict[int, bytes] = {}
    for raw_entry in value.split(";"):
        entry = raw_entry.strip()
        if not entry:
            raise ValueError("Manufacturer data contains an empty entry")
        company_id_text, separator, hex_data = entry.partition(":")
        if not separator or not company_id_text.strip() or not hex_data.strip():
            raise ValueError("Manufacturer data must use COMPANY_ID:HEX_DATA format")
        try:
            company_id = int(company_id_text.strip(), 0)
        except ValueError as err:
            raise ValueError(f"Invalid manufacturer company ID: {company_id_text}") from err
        if not 0 <= company_id <= 0xFFFF:
            raise ValueError("Manufacturer company ID must be between 0 and 65535")
        try:
            payload = bytes.fromhex(hex_data)
        except ValueError as err:
            raise ValueError("Manufacturer payload must contain valid hexadecimal data") from err
        if len(payload) > 252:
            raise ValueError("Manufacturer payload cannot exceed 252 bytes")
        entries[company_id] = payload
    return entries
