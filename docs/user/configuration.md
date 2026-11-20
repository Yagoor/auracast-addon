# Configuration

Every option on the add-on's Configuration tab. Only the controller is required; the rest have
sensible defaults.

The configuration screen shows **Player name**, **Auracast controller** and **Log level** up
front. The others are optional and sit behind **Show unused optional configuration options**, on
purpose: most people never need them.

## At a glance

| Option | Type and range | Default |
| --- | --- | --- |
| {ref}`name <opt-name>` | text | `Auracast` |
| {ref}`auracast_controller <opt-auracast_controller>` | serial device, **required** | — |
| {ref}`broadcast_name <opt-broadcast_name>` | text, 4–32 bytes | the player name |
| {ref}`baudrate <opt-baudrate>` | 9600–4000000 | `1000000` |
| {ref}`buffer_ms <opt-buffer_ms>` | 50–800 ms | `250` |
| {ref}`manufacturer_data <opt-manufacturer_data>` | `ID:HEX;…` | none |
| {ref}`log_level <opt-log_level>` | `debug` / `info` / `warning` / `error` | `info` |
| {ref}`allow_unpaired <opt-allow_unpaired>` | on / off | off |

## Options

(opt-name)=
### Player name (`name`)

Type
: Text. Shown by default.

Default
: Empty, which means `Auracast`.

The name this player shows up under in Music Assistant. It is also the broadcast name unless
{ref}`Broadcast name <opt-broadcast_name>` is set.

(opt-auracast_controller)=
### Auracast controller (`auracast_controller`)

Type
: Serial device (`tty` subsystem). **Required.**

Default
: None; you must choose one.

The Bluetooth LE Audio controller that transmits the broadcast. It has to be a controller flashed
for Auracast, not an ordinary Bluetooth dongle. The add-on only starts with a supported
controller (USB ID `2FE3:0004`), and says which port it refused and why otherwise.

(opt-broadcast_name)=
### Broadcast name (`broadcast_name`)

Type
: Text, 4 to 32 bytes (UTF-8). Optional.

Default
: The player name.

The name headphones and speakers show when they look for a broadcast. The length is counted in
UTF-8 bytes, so accented letters and emoji count for more than one.

```{warning}
When this is empty the player name is used, and it must fit the same 4 to 32 byte rule. A player
name like `Den` with no broadcast name stops the add-on with *The broadcast name must be 4 to 32
bytes long*.
```

(opt-baudrate)=
### Serial baud rate (`baudrate`)

Type
: Whole number, 9600 to 4000000. Optional.

Default
: `1000000`

How fast the add-on talks to the controller over its serial port. Leave it empty unless the
controller's instructions name another rate.

(opt-buffer_ms)=
### Audio buffer (`buffer_ms`)

Type
: Whole number of milliseconds, 50 to 800. Optional.

Default
: `250`

How much audio the player collects before it starts transmitting, and again after the audio runs
dry. Raise it if you hear clicks or short dropouts, at the cost of a slightly later start when a
track begins. The log says *Audio underrun N* each time the audio runs dry.

(opt-manufacturer_data)=
### Manufacturer data (`manufacturer_data`)

Type
: Text: `COMPANY_ID:HEX_DATA` entries separated by `;`. Optional.

Default
: Empty, which adds nothing.

Advanced; most people can leave this empty. It adds manufacturer-specific data to the broadcast's
advertising, which some receivers use.

- Company IDs are decimal unless prefixed with `0x`, and must be 0 to 65535.
- The data is hexadecimal, at most 252 bytes per entry.
- Example: `0x0059:0102`, or two entries: `0x0059:0102;89:ABCD`.

(opt-log_level)=
### Log level (`log_level`)

Type
: One of `debug`, `info`, `warning`, `error`. Shown by default.

Default
: `info`

How much the player writes to its log. Raise it to `debug` while chasing a problem, and put it
back afterwards. It applies to the player's own messages; the libraries underneath (Bumble,
serial, Sendspin) stay at `info` or above, because at debug they log every packet.

(opt-allow_unpaired)=
### Let unpaired servers play (`allow_unpaired`)

Type
: On / off. Optional.

Default
: Off

Off by default, and best left off: a server has to [pair](pairing.md) with the player before it
can play on it. Turn it on only to let any server on your network play here without pairing; the
log then warns *Any server on the network may play here without pairing*.

## Example in YAML

The same options in the Configuration tab's **Edit in YAML** view:

```yaml
name: Living room
auracast_controller: /dev/serial/by-id/usb-…-if00
broadcast_name: Living room TV
buffer_ms: 300
log_level: info
```

## What the add-on keeps

Besides the options, the add-on keeps a few things in its data folder so they survive restarts
and updates:

- `identity.key`: the player's Sendspin identity, readable by the add-on only.
- `pairing.json`: the servers paired with the player.
- `state.json`: the Bluetooth address, the 24-bit broadcast ID, volume, mute and the output delay
  Music Assistant last set.
