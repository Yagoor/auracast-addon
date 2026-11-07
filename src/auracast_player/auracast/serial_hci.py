"""
Serial port handling for the HCI controller.

Opens the controller as a Bumble transport through serialx, with exclusive access and DTR
asserted.
"""

from __future__ import annotations

import asyncio
from typing import cast

import serialx
from bumble.transport.common import StreamPacketSink, StreamPacketSource, Transport


class SerialHciSource(StreamPacketSource):
    """Feed HCI packets read from a serial transport into Bumble."""

    def connection_lost(self, exc: Exception | None) -> None:
        """Report a lost serial connection to the Bumble host."""
        self.on_transport_lost()


async def open_hci_transport(port: str, baudrate: int) -> Transport:
    """
    Open a serial port as a Bumble HCI transport with exclusive access.

    Raises `serialx.SerialException` or `OSError` when the port cannot be opened, for example
    because another process holds it.

    :param port: Path to the controller's UART device.
    :param baudrate: UART baud rate.
    """
    serial_transport, source = await serialx.create_serial_connection(
        asyncio.get_running_loop(),
        SerialHciSource,
        port,
        baudrate=baudrate,
        exclusive=True,
    )
    try:
        # Zephyr's HCI UART sample, like Bumble's own serial transport, expects DTR asserted
        await serial_transport.set_modem_pins(dtr=True)
    except serialx.UnsupportedSetting:
        pass
    except BaseException:
        serial_transport.close()
        raise
    return Transport(cast("SerialHciSource", source), StreamPacketSink(serial_transport))
