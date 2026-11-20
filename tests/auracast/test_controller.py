"""Tests for describing a controller."""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING

from auracast_player.auracast import controller
from auracast_player.auracast.controller import ControllerInfo, find_unsupported_controller

if TYPE_CHECKING:
    import pytest


def local_version(**overrides: int) -> SimpleNamespace:
    """Build HCI local-version parameters, by default a Core 5.2 controller from Harman."""
    values = {
        "hci_version": 11,
        "hci_subversion": 0x1234,
        "lmp_version": 11,
        "lmp_subversion": 0x5678,
        "company_identifier": 0x0057,
    }
    return SimpleNamespace(**{**values, **overrides})


def test_controller_info_names_the_manufacturer_model_and_firmware() -> None:
    """Turn what the controller reports into what a person recognises."""
    info = ControllerInfo.from_local_version(local_version())

    assert info.manufacturer == "Harman International Industries, Inc."
    assert info.model == "Bluetooth Core 5.2 controller"
    assert info.firmware == "0x5678"
    assert "company ID 0x0057" in info.stack


def test_controller_info_copes_with_unknown_company_and_version() -> None:
    """Leave the manufacturer unset, and fall back to the raw HCI version."""
    info = ControllerInfo.from_local_version(
        local_version(company_identifier=0xFFFE, hci_version=99)
    )

    assert info.manufacturer is None
    assert info.model == "HCI version 99 controller"


def test_find_unsupported_controller_checks_the_usb_id(monkeypatch: pytest.MonkeyPatch) -> None:
    """Accept the supported VID:PID, name any other, and refuse a path that is no port."""
    ports = [
        SimpleNamespace(resolved_device="/dev/ttyACM0", vid=0x2FE3, pid=0x0004),
        SimpleNamespace(resolved_device="/dev/ttyACM1", vid=0x1915, pid=0x520F),
        SimpleNamespace(resolved_device="/dev/ttyAMA0", vid=None, pid=None),
    ]
    monkeypatch.setattr(controller.serialx, "list_serial_ports", lambda: ports)

    assert find_unsupported_controller("/dev/ttyACM0") is None
    assert "1915:520F" in (find_unsupported_controller("/dev/ttyACM1") or "")
    assert "not a USB device" in (find_unsupported_controller("/dev/ttyAMA0") or "")
    assert "not a serial port" in (find_unsupported_controller("/dev/ttyUSB9") or "")
