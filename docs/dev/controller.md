# Controllers

The controller is checked twice: by USB ID before anything is opened, and by capability once it
answers over HCI.

## Supported controllers

| USB ID (VID:PID) | Notes |
| --- | --- |
| `2FE3:0004` | The only supported ID today. `2FE3` is the USB vendor ID Zephyr RTOS uses by default; the serial transport asserts DTR, as Zephyr's HCI UART sample and Bumble's own serial transport expect. |

The list is {py:data}`~auracast_player.auracast.controller.SUPPORTED_USB_IDS` in
`src/auracast_player/auracast/controller.py`.

## Stage 1: the USB ID check

The Supervisor can only filter the controller picker by subsystem (`device(subsystem=tty)`), so
any serial device can be selected. Before logging is even configured, `main()` calls
{py:func}`~auracast_player.auracast.controller.find_unsupported_controller`:

1. Resolve the chosen path with `os.path.realpath`, so a `/dev/serial/by-id/…` link matches its
   `/dev/ttyACM*` target.
2. List the system's serial ports with `serialx.list_serial_ports()` and find the one whose
   resolved device matches.
3. Return `None` if its `(vid, pid)` is in `SUPPORTED_USB_IDS`; otherwise a message naming the
   port and its ID, or *not a USB device*.
4. If no port matches, return *… is not a serial port on this system*.

A message exits the process with code 1, which the s6 `finish` script turns into a stopped
container.

## Stage 2: the capability check

After `Device.power_on()`,
{py:func}`~auracast_player.auracast.controller.find_missing_auracast_support` checks the
controller reports everything a broadcast needs:

| LE features | HCI commands |
| --- | --- |
| LE Extended Advertising | LE Create BIG |
| LE Periodic Advertising | LE Terminate BIG |
| Isochronous Broadcaster | LE Setup ISO Data Path |
| | LE Read Buffer Size V2 |

Anything missing raises Bumble's `NotSupportedError` listing it, and the broadcast is torn down.

## What the controller reports

{py:meth}`ControllerInfo.from_local_version() <auracast_player.auracast.controller.ControllerInfo.from_local_version>`
turns the HCI *Read Local Version Information* response into what Music Assistant shows for the
player's device:

manufacturer
: The company identifier, looked up in Bumble's table.

model
: *Bluetooth Core X.Y controller*, or *HCI version N controller* when Bumble has no name for it.

firmware
: The LMP subversion, as `0xNNNN`.

The full stack string, with company ID, HCI revision and LMP version, is logged at debug level.

## Adding a controller

To support another controller, it must work as a USB serial HCI controller with the features
above. Then:

1. Add its `(vid, pid)` tuple to `SUPPORTED_USB_IDS` in
   `src/auracast_player/auracast/controller.py`.
2. Extend `tests/auracast/test_controller.py` with a case for the new ID.
3. Check its device node matches the AppArmor rule `/dev/tty{ACM,USB,AMA,S}[0-9]* rwk` in
   `auracast/apparmor.txt`; widen it if not.
4. If it needs another baud rate, document it; the default is 1 000 000. If it must not have DTR
   asserted, `serial_hci.py` is where that is set.
5. Update the USB ID in `auracast/translations/en.yaml` (the controller option's description),
   `auracast/README.md` and these docs, and add a `CHANGELOG.md` entry.
6. Test on hardware: the add-on starts, the log says *Broadcasting … with 2 BIS streams*, and a
   receiver plays audio.
