# Troubleshooting

When the add-on cannot run it stops with a message saying why. Start with the add-on's **Log**
tab.

If the player exits with an error the whole add-on stops rather than restarting forever, because
the options cannot change between attempts. The log then ends with a line like
`auracast-player exited 1; stopping the container.`, and the reason is the line just above it.

## "… is not a supported Auracast controller"

```text
Auracast player: /dev/ttyACM0 (10C4:EA60) is not a supported Auracast controller
```

The selected serial port belongs to a device whose USB ID is not on the supported list. Only
`2FE3:0004` is supported today. The ID in brackets is the device you picked; `not a USB device`
there means it is not a USB serial port at all.

- Check you picked the right entry under **Auracast controller**. Other serial devices, such as
  Zigbee or Z-Wave sticks, show up in the same list.
- Make sure the controller runs Auracast firmware. A controller flashed with something else may
  report another USB ID.

## "… is not a serial port on this system"

```text
Auracast player: /dev/serial/by-id/usb-… is not a serial port on this system
```

The controller you selected is not there. It was unplugged, it is plugged into another port and
the old path is gone, or the host has not finished detecting it.

- Plug the controller in, wait a few seconds, and open the Configuration tab again to re-select
  it.
- Prefer a `/dev/serial/by-id/…` path, which stays the same whichever USB port the controller is
  in.
- On a virtual machine, check the USB device is passed through to the Home Assistant VM.

## "The Bluetooth controller does not support Auracast broadcasting"

```text
The Auracast broadcast stopped: The Bluetooth controller does not support Auracast broadcasting: missing Isochronous Broadcaster, LE Create BIG
```

The controller opened, but it lacks features a broadcast needs. The message lists what is
missing. Re-flash it with firmware that supports LE Audio broadcast.

## The controller cannot be opened

If the log says *The Auracast broadcast stopped:* followed by a serial or OS error, the port
could not be opened or the controller stopped answering. The add-on opens the port exclusively,
so another add-on or integration that holds the same serial port will block it. Check nothing
else is configured to use the controller, then unplug it, plug it back in and restart the
add-on.

If **Serial baud rate** is set, try clearing it so the default of 1000000 applies, unless the
controller's instructions say otherwise.

## Option errors

| Message | Fix |
| --- | --- |
| *The broadcast name must be 4 to 32 bytes long* | Set a {ref}`Broadcast name <opt-broadcast_name>` of 4 to 32 bytes, or a longer player name. |
| *The manufacturer data cannot be used: …* | Use `COMPANY_ID:HEX_DATA`, separated by `;`, with no empty entries. See {ref}`Manufacturer data <opt-manufacturer_data>`. |
| *Select the Auracast controller in the add-on configuration* | Choose the controller on the Configuration tab. |

## Clicks and dropouts

```text
Audio underrun 3: the server did not deliver audio fast enough, buffering again before resuming
```

Audio arrived from Music Assistant later than the radio needed it. The player stops sending for a
moment so receivers conceal the gap, buffers again, and resumes. Raise
{ref}`Audio buffer <opt-buffer_ms>` (for example to 400 ms) and check the network between Music
Assistant and Home Assistant, Wi-Fi in particular.

## The player does not appear in Music Assistant

- Check the add-on log ends with *Advertising "…" over mDNS, waiting for Music Assistant*. If it
  stopped earlier, fix the error above that line first.
- Music Assistant has to be on the same local network: discovery is mDNS, and Music Assistant
  connects in on TCP port `8928`.
- Music Assistant's Sendspin support must be built on `aiosendspin` 10 or later.

## Music Assistant cannot play to the player

A server must [pair](pairing.md) first. If the token is no longer in the log, a server has
already paired; pair another one with a [6-digit code](pairing.md#with-a-6-digit-code).

(apparmor-debugging)=
## AppArmor denials

The add-on runs under its own AppArmor profile, which allows only what the player needs. If a
rule is missing, the symptom is usually a failed start or a controller that cannot be opened,
with a permission error in the log. On the host, AppArmor denials are in the audit log:

```sh
journalctl _TRANSPORT="audit" -g 'apparmor="DENIED"'
```

To find every missing rule at once, run a local copy of the add-on with the profile in
*complain* mode: add `complain` to the outer profile's flags in `apparmor.txt`, so it reads
`flags=(attach_disconnected,mediate_deleted,complain)`. Use the add-on, then list what the profile
would have refused:

```sh
journalctl _TRANSPORT="audit" -g 'apparmor="ALLOWED"'
```

Please [open an issue](https://github.com/Yagoor/auracast-addon/issues) with those lines. See
[AppArmor and security](../dev/security.md) for how the profile is laid out.

## Getting more detail

Set {ref}`Log level <opt-log_level>` to `debug` and restart. The log then shows the controller's
HCI version and features, the broadcast parameters, and every change between idle, buffering and
playing. Put it back to `info` afterwards.
