# Module tour

What lives where in `src/auracast_player/` and in the repository. The
[API reference](api.md) has every class and function.

## The package

| File | What it does |
| --- | --- |
| `__main__.py` | Composition root. Parses `--options` and `--state-dir`, validates, checks the controller, runs everything under `asyncio`, handles signals and exit codes. |
| `constants.py` | Defaults and ranges for the options, and the audio format: 48 kHz, 2 channels, 16-bit, 10 ms frames. |
| `logs.py` | Applies the add-on's log level to `auracast_player` only; libraries stay at `INFO` or above. |
| `config/options.py` | `Options` and `load_options()`/`parse_options()`: reads `/data/options.json`, applies defaults, validates ranges, parses `manufacturer_data`. Raises `OptionsError` naming the first bad option. |
| `config/state.py` | `PlayerState` and the files under `/data`: `state.json`, `identity.key`, and the name of `pairing.json`. Writes are atomic (temporary file and `os.replace`) and owner-only. |
| `sendspin/player.py` | `SendspinPlayer`: advertises over mDNS via `ClientListener`, accepts the server's websocket, declares PCM-only support with the transmitter's buffer capacity, and routes audio, stream end/clear, volume, mute and output-delay commands. |
| `sendspin/pairing.py` | `Pairing`: applies `allow_unpaired` to the pairing store, creates a PSK and logs the `SP:0…` token while nothing is paired, and logs the 6-digit code a server asks for. |
| `audio/pcm.py` | `FrameBuffer` (whole 10 ms frames, capped, drops the oldest on overflow), `volume_gain()` (`(v/100) ** 1.5`) and `apply_gain()`. |
| `audio/phase.py` | `Phase`, a python-statemachine `StateMachine`: idle, buffering, playing, counting underruns. |
| `audio/transmitter.py` | `Transmitter`, the paced loop that feeds the broadcast, and the `FrameSink` protocol. See [Audio pipeline](audio.md). |
| `auracast/broadcaster.py` | `AuracastBroadcaster` and `BroadcastConfig`: LC3 encoding, Bumble device, advertising set, BIG, ISO streams, ordered teardown. |
| `auracast/advertising.py` | Builds the extended advertising data (names, manufacturer data, Broadcast Audio Announcement, Public Broadcast Announcement) and the periodic data (the BASE: LC3 setup and channel allocation per BIS). |
| `auracast/controller.py` | `SUPPORTED_USB_IDS`, `find_unsupported_controller()`, `find_missing_auracast_support()` and `ControllerInfo`. See [Controllers](controller.md). |
| `auracast/serial_hci.py` | `open_hci_transport()`: opens the port through serialx with `exclusive=True`, asserts DTR, and wraps it as a Bumble transport. |

## Runtime dependencies

Pinned exactly in `pyproject.toml`; Python 3.14 or later.

| Package | Used for |
| --- | --- |
| `aiosendspin==10.2.2` | The Sendspin client, listener, Noise encryption and pairing store. |
| `bumble==0.0.235` | Bluetooth host stack: HCI, extended and periodic advertising, BIG, ISO streams, LE Audio data structures. |
| `lc3py` (liblc3 `v1.1.3`) | LC3 encoder; built from source, as it has no wheel. |
| `serialx==1.15.1` | Async serial port with exclusive open, modem pins and port listing (USB VID/PID). |
| `python-statemachine==3.2.2` | The transmitter's `Phase`. |

## The repository

| Path | Contents |
| --- | --- |
| `auracast/` | The add-on as the Supervisor sees it: `config.yaml`, `translations/en.yaml`, `apparmor.txt`, `README.md`, `CHANGELOG.md`, icon and logos. |
| `repository.yaml` | Makes the repository an add-on repository. |
| `src/auracast_player/` | The player. |
| `tests/` | The pytest suite, mirroring the package layout. |
| `Dockerfile` | Two-stage build on the Home Assistant Debian base. |
| `rootfs/` | The s6-overlay service and the container healthcheck. |
| `scripts/` | `smoke_test.sh` and `release_notes.sh`. |
| `docs/` | This documentation (Sphinx, MyST Markdown); `docs/design/` holds the diagram sources. |
| `.github/` | CI (`build.yml`), releases (`release.yml`), docs (`pages.yml`), Dependabot. |
