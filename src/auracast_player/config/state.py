"""State the player keeps across restarts, in the add-on's data directory."""

from __future__ import annotations

import json
import os
import secrets
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from aiosendspin.noise import Identity
from bumble import hci

DEFAULT_STATE_DIR = Path("/data")
IDENTITY_FILE = "identity.key"
PAIRING_FILE = "pairing.json"
STATE_FILE = "state.json"


def generate_device_address() -> str:
    """Return a new random static Bluetooth device address."""
    return str(hci.Address.generate_static_address())


def parse_device_address(value: object) -> str | None:
    """
    Return the canonical form of a stored static device address.

    :param value: The stored value, which may be missing or malformed.
    """
    if not isinstance(value, str):
        return None
    try:
        address = hci.Address(value)
    except ValueError:
        return None
    return str(address) if address.is_static else None


@dataclass(slots=True)
class PlayerState:
    """Values that must survive a restart so receivers and servers keep recognising the player."""

    device_address: str = field(default_factory=generate_device_address)
    broadcast_id: int = field(default_factory=lambda: secrets.randbelow(0xFFFFFF) + 1)
    volume: int = 100
    muted: bool = False
    output_delay_ms: float = 0.0


def load_identity(state_dir: Path) -> Identity:
    """
    Load the player's Sendspin identity, creating it on first start.

    :param state_dir: The directory holding the player's state.
    """
    path = state_dir / IDENTITY_FILE
    try:
        return Identity.from_private_bytes(bytes.fromhex(path.read_text(encoding="ascii").strip()))
    except OSError, ValueError:
        identity = Identity.generate()
        _write_private(path, identity.private_bytes.hex())
        return identity


def load_state(state_dir: Path) -> PlayerState:
    """
    Load the saved state, replacing anything missing or malformed with a fresh value.

    :param state_dir: The directory holding the player's state.
    """
    try:
        raw: Any = json.loads((state_dir / STATE_FILE).read_text(encoding="utf-8"))
    except OSError, ValueError:
        raw = {}
    if not isinstance(raw, dict):
        raw = {}
    state = PlayerState()
    if (address := parse_device_address(raw.get("device_address"))) is not None:
        state.device_address = address
    broadcast_id = raw.get("broadcast_id")
    if (
        isinstance(broadcast_id, int)
        and not isinstance(broadcast_id, bool)
        and 0 < broadcast_id < 0x1000000
    ):
        state.broadcast_id = broadcast_id
    volume = raw.get("volume")
    if isinstance(volume, int) and not isinstance(volume, bool):
        state.volume = max(0, min(100, volume))
    state.muted = raw.get("muted") is True
    delay = raw.get("output_delay_ms")
    if isinstance(delay, int | float) and not isinstance(delay, bool) and delay >= 0:
        state.output_delay_ms = float(delay)
    return state


def save_state(state_dir: Path, state: PlayerState) -> None:
    """
    Save the state atomically.

    :param state_dir: The directory holding the player's state.
    :param state: The values to keep.
    """
    payload = {
        "device_address": state.device_address,
        "broadcast_id": state.broadcast_id,
        "volume": state.volume,
        "muted": state.muted,
        "output_delay_ms": state.output_delay_ms,
    }
    _write_private(state_dir / STATE_FILE, json.dumps(payload))


def _write_private(path: Path, content: str) -> None:
    """Write a file readable by its owner only, replacing any previous one atomically."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
        os.replace(temporary, path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise
