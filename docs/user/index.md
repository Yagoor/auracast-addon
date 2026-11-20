# Overview

The Auracast add-on turns a Bluetooth LE Audio controller on the machine running Home Assistant
into a Music Assistant player that broadcasts over Auracast.

Anyone with an Auracast receiver in range, such as headphones, a speaker or a hearing aid, can
join the broadcast. The player speaks [Sendspin](https://sendspin-audio.com), the playback
protocol built into Music Assistant, so it appears in Music Assistant by itself and needs nothing
enabled there.

## Requirements

| What | Details |
| --- | --- |
| Home Assistant | An installation with add-ons (the Supervisor), on an `amd64` or `aarch64` machine. |
| Music Assistant | A version whose Sendspin support is built on `aiosendspin` 10 or later, on the same local network as the add-on. |
| Bluetooth controller | A Bluetooth LE Audio controller flashed for Auracast, connected over USB. Only USB ID `2FE3:0004` is supported today. An ordinary Bluetooth dongle, or the computer's built-in Bluetooth, will not work. |
| Receivers | Any Auracast receiver: headphones, earbuds, speakers or hearing aids that can join a public broadcast. |

### About the controller

The add-on talks to the controller as a serial HCI device: the Bluetooth host stack
([Bumble](https://github.com/google/bumble)) runs inside the add-on and drives the controller
directly over its USB serial port. It does not use the host's Bluetooth stack (BlueZ) at all, so
the controller is dedicated to this add-on while it runs.

At startup the add-on checks the selected port's USB vendor and product ID and refuses anything
other than `2FE3:0004`. Once the controller is open it also checks that it really can broadcast:
it needs LE Extended Advertising, LE Periodic Advertising and the Isochronous Broadcaster
feature, plus the HCI commands to create a broadcast. See [Controllers](../dev/controller.md) for
the details.

## What you get

- A player in Music Assistant, named after the {ref}`Player name <opt-name>` option, with volume
  and mute.
- A public Auracast broadcast, 48 kHz stereo LC3, under the
  {ref}`Broadcast name <opt-broadcast_name>`.
- Encrypted, paired connections between Music Assistant and the player.
- The player's identity, broadcast ID and Bluetooth address kept across restarts and updates, so
  receivers and servers keep recognising it.

## Known limits

- Receivers join the broadcast themselves. Music Assistant does not see or control them.
- The player does not yet line its audio up with other Sendspin players, so do not group it with
  players you listen to in the same room.
- One controller carries one broadcast.
- The broadcast is not encrypted: there is no broadcast code option, so anyone in range can
  listen.
