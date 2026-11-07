"""How servers pair with this player, and how the user is told to pair."""

from __future__ import annotations

import logging
from dataclasses import replace
from typing import TYPE_CHECKING

from aiosendspin.noise.keys import generate_psk, psk_id_for
from aiosendspin.noise.pairing_token import PSKPairingToken, encode_psk_token
from aiosendspin.noise.trust_store import PairingPsk

if TYPE_CHECKING:
    from aiosendspin.noise.trust_store import FileClientPairingStore

LOGGER = logging.getLogger(__name__)


class Pairing:
    """Apply the pairing policy, and tell the user how to pair while nothing is paired."""

    def __init__(self, *, allow_unpaired: bool) -> None:
        """
        Create the pairing policy.

        :param allow_unpaired: Whether servers that have not paired may play here.
        """
        self._allow_unpaired = allow_unpaired

    async def configure(self, store: FileClientPairingStore, client_id: str) -> None:
        """
        Apply the policy to the pairing store, and log the pairing token while it is unpaired.

        :param store: The store holding the paired servers.
        :param client_id: This player's peer ID, which the pairing token carries.
        """
        config = await store.get_pairing_config()
        wanted = replace(config, unpaired_access_enabled=self._allow_unpaired)
        if wanted != config:
            await store.store_pairing_config(wanted)
        if self._allow_unpaired:
            LOGGER.warning("Any server on the network may play here without pairing")
        if await store.list_records():
            return
        psk = await store.pairing_psk()
        if psk is None:
            raw = generate_psk()
            psk = PairingPsk(psk_id_for(raw), raw)
            await store.set_pairing_psk(psk)
        LOGGER.info(
            "No server is paired yet. Pairing token %s",
            encode_psk_token(PSKPairingToken(client_id, psk.psk)),
        )

    async def show_code(self, pairing_code: str | None, *, grouped: str | None) -> None:
        """Log the pairing code a server asked for, so it can be typed into Music Assistant."""
        if grouped is not None:
            LOGGER.info("*** Pairing code: %s ***", grouped)
