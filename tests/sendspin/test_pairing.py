"""Tests for the pairing policy."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pytest
from aiosendspin.noise import Identity
from aiosendspin.noise.trust_store import FileClientPairingStore

from auracast_player.sendspin.pairing import Pairing

if TYPE_CHECKING:
    from pathlib import Path

CLIENT_ID = Identity.generate().peer_id


@pytest.mark.asyncio
async def test_pairing_token_is_logged_until_a_server_is_paired(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Show the token while nothing is paired, and keep it the same across restarts."""
    pairing = Pairing(allow_unpaired=False)
    store = await FileClientPairingStore.open(tmp_path / "pairing.json")

    with caplog.at_level(logging.INFO, logger="auracast_player.sendspin.pairing"):
        await pairing.configure(store, CLIENT_ID)
        first = [r.getMessage() for r in caplog.records if "Pairing token" in r.getMessage()]
        caplog.clear()
        reopened = await FileClientPairingStore.open(tmp_path / "pairing.json")
        await pairing.configure(reopened, CLIENT_ID)
        second = [r.getMessage() for r in caplog.records if "Pairing token" in r.getMessage()]

    assert len(first) == 1
    assert first == second


@pytest.mark.asyncio
async def test_unpaired_access_follows_the_option(tmp_path: Path) -> None:
    """Allow servers that have not paired only when the option says so."""
    closed = Pairing(allow_unpaired=False)
    store = await FileClientPairingStore.open(tmp_path / "closed.json")
    await closed.configure(store, CLIENT_ID)
    assert (await store.get_pairing_config()).unpaired_access_enabled is False

    opened = Pairing(allow_unpaired=True)
    other = await FileClientPairingStore.open(tmp_path / "open.json")
    await opened.configure(other, CLIENT_ID)
    assert (await other.get_pairing_config()).unpaired_access_enabled is True
