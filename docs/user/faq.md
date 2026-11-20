# FAQ

## Can I use my computer's built-in Bluetooth or a normal USB dongle?

No. The add-on needs a Bluetooth LE Audio controller flashed for Auracast and reachable as a USB
serial HCI device. Only USB ID `2FE3:0004` is supported today, and the add-on refuses to start
with anything else.

## Does it use Home Assistant's Bluetooth integration?

No. The add-on runs its own Bluetooth host stack (Bumble) and talks to the controller over its
serial port. It does not go through BlueZ or the Bluetooth integration, and the controller is
dedicated to the add-on.

## How many receivers can listen?

A broadcast has no connections, so the add-on does not limit how many receivers join. Anyone in
radio range with an Auracast receiver can listen.

## Can I protect the broadcast with a code?

Not today. The broadcast is public and unencrypted; there is no broadcast code option.
Connections between Music Assistant and the player are encrypted and paired.

## Can I run two broadcasts?

One controller carries one broadcast, and the add-on runs one player.

## Can I group it with my other Music Assistant speakers?

You can, but it does not yet line its audio up with other Sendspin players. Do not group it with
players you listen to in the same room.

## What audio quality does the broadcast use?

48 kHz, 16-bit stereo, encoded with LC3 in 10 ms frames at 160 kbit/s, sent as two broadcast
streams (front left and front right).

## Does Music Assistant control the headphones' volume?

Music Assistant's volume and mute scale the audio before it is broadcast, so they affect every
listener. Receivers keep their own volume controls, and Music Assistant does not see which
receivers are listening.

## Will my receivers need to re-pair after an update?

No. The broadcast ID and Bluetooth address are kept in the add-on's data, as is the Sendspin
pairing, so receivers and Music Assistant keep recognising the player.

## Which architectures are supported?

`amd64` and `aarch64`.

## Where do I report a bug?

In the [GitHub issues](https://github.com/Yagoor/auracast-addon/issues). Include the add-on log,
ideally at `debug` level.
