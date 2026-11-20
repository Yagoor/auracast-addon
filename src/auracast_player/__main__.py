"""Entry point: run the Sendspin player and the Auracast broadcast until stopped."""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import logging
import signal
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from aiosendspin.models import DeviceInfo

from .audio.transmitter import Transmitter
from .auracast.broadcaster import BROADCAST_ERRORS, AuracastBroadcaster, BroadcastConfig
from .auracast.controller import find_unsupported_controller
from .config.options import DEFAULT_OPTIONS_FILE, Options, OptionsError, load_options
from .config.state import DEFAULT_STATE_DIR, load_state, save_state
from .logs import configure_logging
from .sendspin.player import SendspinPlayer

if TYPE_CHECKING:
    from collections.abc import Sequence

LOGGER = logging.getLogger("auracast_player")


async def run(options: Options, state_dir: Path) -> None:
    """
    Broadcast until a signal asks the player to stop, or the broadcast fails.

    :param options: The validated add-on options.
    :param state_dir: The directory holding the player's state.
    """
    state = load_state(state_dir)
    save_state(state_dir, state)
    broadcaster = AuracastBroadcaster(
        BroadcastConfig(
            name=options.broadcast_name,
            serial_port=options.controller,
            baudrate=options.baudrate,
            manufacturer_data=options.manufacturer_data,
            broadcast_id=state.broadcast_id,
            device_address=state.device_address,
        )
    )
    transmitter = Transmitter(broadcaster, state, options.buffer_ms)
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for signum in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(signum, stop.set)

    await broadcaster.start()
    controller = broadcaster.controller
    device_info = (
        DeviceInfo(
            manufacturer=controller.manufacturer,
            product_name=controller.model,
            software_version=controller.firmware,
        )
        if controller
        else None
    )
    player = SendspinPlayer(options, state, state_dir, transmitter, device_info)
    transmit = asyncio.create_task(transmitter.run(), name="transmit")
    try:
        await player.start()
        stopped = asyncio.create_task(stop.wait(), name="stop")
        await asyncio.wait({transmit, stopped}, return_when=asyncio.FIRST_COMPLETED)
        stopped.cancel()
        if transmit.done() and not transmit.cancelled():
            transmit.result()
    finally:
        transmit.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await transmit
        await player.stop()
        await broadcaster.stop()


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """
    Read the command line.

    :param argv: The arguments after the program name; the process arguments when ``None``.
    """
    parser = argparse.ArgumentParser(prog="auracast-player", description=__doc__)
    parser.add_argument("--options", type=Path, default=DEFAULT_OPTIONS_FILE, help="options file")
    parser.add_argument("--state-dir", type=Path, default=DEFAULT_STATE_DIR, help="state directory")
    return parser.parse_args(argv)


def main() -> None:
    """Read the options and run the player; exit non-zero when it cannot run."""
    args = parse_args()
    try:
        options = load_options(args.options)
    except OptionsError as err:
        sys.exit(f"Auracast player: {err}")
    if problem := find_unsupported_controller(options.controller):
        sys.exit(f"Auracast player: {problem}")
    configure_logging(options.log_level)
    try:
        asyncio.run(run(options, args.state_dir))
    except BROADCAST_ERRORS as err:
        LOGGER.error("The Auracast broadcast stopped: %s", err)
        sys.exit(1)


if __name__ == "__main__":
    main()
