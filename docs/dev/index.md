# Architecture

One Python process, `auracast-player`, runs under s6-overlay in the add-on container. It is a
Sendspin client on one side and a Bluetooth LE Audio broadcaster on the other, with a paced
transmitter in between.

## The audio path

```text
Music Assistant (Sendspin server)
  │ PCM 48 kHz, 16-bit stereo
  │ encrypted websocket, port 8928
  ▼
SendspinPlayer
  │ feed(pcm) / clear()
  ▼
Transmitter
  │ send_pcm() / send_silence()
  │ ≤ 80 ms queued at the controller
  ▼
AuracastBroadcaster
  │ LC3 as ISO packets, HCI over serial
  ▼
LE Audio controller (USB 2FE3:0004)
  │ BIS 1 (left) + BIS 2 (right)
  ▼
Auracast receivers
```

`__main__.run()` creates the three objects and wires them together.

## Class design

The package is split by side. The sides only meet through two small protocols, `AudioSink` and
`FrameSink`, which is what lets each side be tested with a fake for the other.

```{uml} /design/classes.puml
:alt: Class diagram of the Auracast player, grouped into the config, sendspin, audio and auracast packages, with the external aiosendspin, bumble, python-statemachine, lc3py and serialx classes they use.
```

Key relationships:

- `__main__` is the composition root: it loads `Options` and `PlayerState`, and creates the
  `AuracastBroadcaster`, the `Transmitter` and the `SendspinPlayer`.
- `SendspinPlayer` owns an aiosendspin `SendspinClient`, a `ClientListener` and a `Pairing`, and
  calls the `AudioSink` (the transmitter).
- `Transmitter` owns a `FrameBuffer` and a `Phase`, reads volume and mute from `PlayerState` on
  every frame, and writes to the `FrameSink` (the broadcaster).
- `AuracastBroadcaster` opens the controller through `open_hci_transport()` (serialx), drives
  Bumble's `Device`, `Big` and `IsoPacketStream`, and encodes with lc3py's `Encoder`.

## Transmitter states

```{uml} /design/transmitter_states.puml
:alt: State diagram: IDLE goes to BUFFERING on begin; BUFFERING goes to PLAYING on ready; PLAYING goes back to BUFFERING on starve; BUFFERING and PLAYING go to IDLE on reset.
```

The [audio pipeline](audio.md) page explains why the buffering state sends nothing at all.

### Diagram sources

The diagrams are written in PlantUML in `docs/design/*.puml` and rendered to SVG on every docs
build by `sphinxcontrib-plantuml`, so a `.puml` is the only thing to edit. Building the docs
locally needs `plantuml` on the `PATH` (with Java and Graphviz), for example
`brew install plantuml` or `apt install plantuml`; set `PLANTUML` to use another command, such as
`java -jar plantuml.jar`.

## Startup and shutdown

1. **Options.** `main()` reads `/data/options.json` (written by the Supervisor) and validates it.
   Any problem exits with a one-line message before logging is set up.
2. **Controller check.** `find_unsupported_controller()` refuses a port whose USB ID is not
   supported, or that does not exist.
3. **State.** `state.json` is loaded (fresh values replace anything missing or malformed) and
   saved straight back, so a new address and broadcast ID are fixed from the first start.
4. **Broadcast.** `AuracastBroadcaster.start()` opens the serial port exclusively, powers on
   Bumble, reads the controller's version, checks its LE Audio support, and creates the
   advertising set, periodic advertising and the BIG.
5. **Sendspin.** `SendspinPlayer.start()` loads the identity, opens the pairing store, logs the
   pairing token if nothing is paired, and starts the mDNS-advertised listener.
6. **Run.** `Transmitter.run()` runs as a task until `SIGTERM`/`SIGINT` or a broadcast error.
7. **Stop.** The transmitter is cancelled, the player says goodbye with reason `restart` (so
   Music Assistant keeps redialling) and stops its listener, then the broadcaster terminates the
   BIG, stops advertising, powers off and closes the port. Each teardown step has a 2 s timeout.

Errors from Bumble, liblc3, the serial port and the OS are collected in `BROADCAST_ERRORS`; any
of them ends the process with exit code 1 and the message *The Auracast broadcast stopped: …*.

## In the container

- s6-overlay runs one longrun service, `auracast-player`
  (`rootfs/etc/s6-overlay/s6-rc.d/auracast-player/`), which `exec`s
  `/opt/venv/bin/auracast-player`.
- Its `finish` script halts the container when the player exits with an error, rather than
  letting s6 restart it forever; exit 0 and 256 (stopped by a signal) pass through.
- `S6_KILL_GRACETIME=3000` bounds shutdown inside the Supervisor's default 10 s stop timeout;
  `S6_BEHAVIOUR_IF_STAGE2_FAILS=2` stops the container on a failed start.
- The Docker `HEALTHCHECK` runs `/usr/bin/container-healthcheck`, which opens a TCP connection to
  `127.0.0.1:8928`. The listener starts only after the broadcast is up, so this also covers a
  controller that failed to open.
