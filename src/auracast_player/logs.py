"""Logging setup."""

from __future__ import annotations

import logging

LOG_FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"
PACKAGE_LOGGER = "auracast_player"
# Libraries are kept at this level or above, whatever the add-on's log level is. At debug they
# log every HCI packet and serial read, which buries everything this player says.
LIBRARY_MIN_LEVEL = logging.INFO


def configure_logging(level_name: str) -> None:
    """
    Set up logging so the add-on's log level applies to this player and not to its libraries.

    :param level_name: The add-on's log level, such as ``debug`` or ``info``.
    """
    level = logging.getLevelName(level_name.upper())
    if not isinstance(level, int):
        level = logging.INFO
    logging.basicConfig(level=max(level, LIBRARY_MIN_LEVEL), format=LOG_FORMAT, force=True)
    logging.getLogger(PACKAGE_LOGGER).setLevel(level)
