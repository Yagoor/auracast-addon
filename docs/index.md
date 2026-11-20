# Auracast for Music Assistant

```{image} _static/icon.png
:alt:
:width: 88px
:align: right
```

Turn a Bluetooth LE Audio controller on your Home Assistant machine into a Music Assistant player
that broadcasts over [Auracast](https://www.bluetooth.com/auracast/). Any Auracast headphones,
speaker or hearing aid in range can join.

Music Assistant streams audio to the add-on over [Sendspin](https://sendspin-audio.com), its
built-in playback protocol. The add-on encodes it with LC3 and hands it to the Bluetooth
controller, which transmits it as a public Auracast broadcast. Receivers tune in on their own.

1. **Music Assistant** finds the player over mDNS and streams 48 kHz stereo PCM to it.
2. **The add-on** buffers the audio, applies volume, and encodes 10 ms LC3 frames.
3. **The controller**, plugged in over USB, transmits two broadcast streams: left and right.
4. **Receivers** find the broadcast by name and join it.

```{note}
The add-on is marked `stage: experimental` and runs on `amd64` and `aarch64` only. It starts
only with a supported controller (USB ID `2FE3:0004`).
```

**New here?** Start with the [user guide](user/index.md). **Working on the code?** Read the
[developer guide](dev/index.md).

```{toctree}
:caption: User guide
:maxdepth: 1

user/index
user/install
user/configuration
user/pairing
user/troubleshooting
user/faq
```

```{toctree}
:caption: Developer guide
:maxdepth: 1

dev/index
dev/modules
dev/audio
dev/controller
dev/development
dev/release
dev/security
dev/api
```

Auracast and the Auracast logo are trademarks of the Bluetooth SIG.
