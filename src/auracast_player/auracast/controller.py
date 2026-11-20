"""What a Bluetooth controller is and whether it can broadcast Auracast."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any

import serialx
from bumble import device, hci
from bumble.company_ids import COMPANY_IDENTIFIERS

LOGGER = logging.getLogger(__name__)
# USB (vendor ID, product ID) of the controllers the add-on is known to work with
SUPPORTED_USB_IDS = frozenset({(0x2FE3, 0x0004)})
REQUIRED_LE_FEATURES = {
    "LE Periodic Advertising": hci.LeFeatureMask.LE_PERIODIC_ADVERTISING,
    "LE Extended Advertising": hci.LeFeatureMask.LE_EXTENDED_ADVERTISING,
    "Isochronous Broadcaster": hci.LeFeatureMask.ISOCHRONOUS_BROADCASTER,
}
REQUIRED_HCI_COMMANDS = {
    "LE Create BIG": hci.HCI_LE_CREATE_BIG_COMMAND,
    "LE Terminate BIG": hci.HCI_LE_TERMINATE_BIG_COMMAND,
    "LE Setup ISO Data Path": hci.HCI_LE_SETUP_ISO_DATA_PATH_COMMAND,
    "LE Read Buffer Size V2": hci.HCI_LE_READ_BUFFER_SIZE_V2_COMMAND,
}


def find_missing_auracast_support(controller_device: device.Device) -> tuple[str, ...]:
    """
    Return the LE features and HCI commands a powered-on controller lacks for broadcasting.

    :param controller_device: A Bumble device whose host completed controller initialization.
    """
    missing = [
        name
        for name, feature in REQUIRED_LE_FEATURES.items()
        if not controller_device.supports_le_features(feature)
    ]
    missing.extend(
        name
        for name, op_code in REQUIRED_HCI_COMMANDS.items()
        if not controller_device.host.supports_command(op_code)
    )
    return tuple(missing)


@dataclass(frozen=True, slots=True)
class ControllerInfo:
    """Who made the controller and what it runs, as it reports itself over HCI."""

    manufacturer: str | None
    model: str
    firmware: str
    stack: str

    @classmethod
    def from_local_version(cls, parameters: Any) -> ControllerInfo:
        """
        Describe a controller from its HCI local-version information.

        :param parameters: The controller's ``Read Local Version Information`` return parameters.
        """
        version = _core_version(parameters)
        return cls(
            manufacturer=COMPANY_IDENTIFIERS.get(parameters.company_identifier),
            model=f"{version} controller",
            firmware=f"0x{parameters.lmp_subversion:04X}",
            stack=(
                f"{version}; company ID 0x{parameters.company_identifier:04X}; "
                f"HCI revision 0x{parameters.hci_subversion:04X}; "
                f"LMP version {parameters.lmp_version}; "
                f"firmware revision 0x{parameters.lmp_subversion:04X}"
            ),
        )


def _core_version(parameters: Any) -> str:
    """Name the Bluetooth Core version a controller reports."""
    # Bumble's enum accepts unknown values, naming them "SpecificationVersion[n]"
    name = hci.SpecificationVersion(parameters.hci_version).name or ""
    if not name.startswith("BLUETOOTH_CORE_"):
        LOGGER.debug("Bumble does not have a name for HCI version %d", parameters.hci_version)
        return f"HCI version {parameters.hci_version}"
    return f"Bluetooth Core {name.removeprefix('BLUETOOTH_CORE_').replace('_', '.')}"


def find_unsupported_controller(path: str) -> str | None:
    """
    Explain why the serial port at ``path`` is not a supported controller, or return ``None``.

    :param path: The controller's device path, such as a ``/dev/serial/by-id/`` link.
    """
    resolved = os.path.realpath(path)
    for port in serialx.list_serial_ports():
        if os.path.realpath(port.resolved_device) != resolved:
            continue
        if (port.vid, port.pid) in SUPPORTED_USB_IDS:
            return None
        usb_id = (
            f"{port.vid:04X}:{port.pid:04X}"
            if port.vid is not None and port.pid is not None
            else "not a USB device"
        )
        return f"{path} ({usb_id}) is not a supported Auracast controller"
    return f"{path} is not a serial port on this system"
