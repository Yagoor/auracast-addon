# AppArmor and security

The add-on ships its own AppArmor profile, which raised its Home Assistant security rating from
4 to 5. The player runs in a child profile limited to what it needs.

## What the add-on asks for

| Setting | Why |
| --- | --- |
| `host_network: true` | The mDNS advertisement, and the inbound websocket Music Assistant connects back in on, need the host's network namespace. |
| `uart: true` | Maps the host's serial devices in, which is how the controller is reached. |
| `apparmor.txt` | Loaded by the Supervisor in place of Docker's default profile. |
| No audio | No sound device is mapped and nothing for sound is installed: the audio leaves over the air. |
| `init: false` | The image brings its own s6-overlay v3 init. |

## The profile

`auracast/apparmor.txt` has two levels. The Supervisor renames the outer profile to the add-on's
ID when it loads it.

### Outer profile `auracast`

Home Assistant's s6-overlay template: execute s6 and the shell tools, read and write `/run`,
`/tmp` and `/data`, send signals to stop the service, plus `network inet stream` so the
healthcheck, which runs under this profile, can connect to the player's port. Executing the
player switches to the child profile:

```text
/opt/venv/bin/auracast-player cx -> auracast_player,
```

### Child profile `auracast_player`

| Rule | Why |
| --- | --- |
| `/opt/venv/** mr`, `/opt/python/** mrix` | Its Python and libraries. |
| `/{usr/,}sbin/ldconfig{,.real} ix`, `/etc/ld.so.cache r` | `ctypes.util.find_library`, used to load liblc3 and libc, asks ldconfig where they are. |
| `/data/** rwk`, `/tmp/** rwk` | Options, state, identity, pairing; atomic writes through temporary files. |
| `/dev/tty{ACM,USB,AMA,S}[0-9]* rwk` | The controller's serial port, with locking for exclusive access. |
| `/dev/serial/** r`, `/sys/class/tty/**`, `/sys/devices/**`, `/run/udev/data/** r` | The links and sysfs/udev entries that name the port and its USB ID. |
| `network inet`/`inet6` `stream`/`dgram`, `network netlink raw` | TCP for the websocket, UDP for mDNS, netlink for `ifaddr` to list interfaces. |
| `signal (receive) peer=*_auracast` | Lets s6, in the outer profile, stop it. |

## Changing the profile

If code starts touching a new path, device or socket type, the profile has to allow it, or the
add-on fails on Home Assistant with no local symptom. Check the profile parses:

```sh
apparmor_parser -Q -K auracast/apparmor.txt
```

To find missing rules, add `complain` to the outer profile's flags, install it as a local
add-on, use it, and read what would have been refused from the host's audit log:

```sh
journalctl _TRANSPORT="audit" -g 'apparmor="ALLOWED"'
```

Add the rules, remove `complain`, and check for denials:

```sh
journalctl _TRANSPORT="audit" -g 'apparmor="DENIED"'
```

## Security rating

Home Assistant scores every add-on and shows the rating on its card. A custom AppArmor profile
raised this one from 4 to 5. Host networking counts against the score, and the add-on cannot do
without it: both discovery and the server's connection depend on it.

## Data and connections

- Sendspin connections are encrypted (Noise, through aiosendspin) and, unless `allow_unpaired`
  is on, only paired servers may play.
- `identity.key` and `state.json` are written atomically and readable by their owner only.
- The pairing token is logged only while nothing is paired; treat it as a secret.
- The Auracast broadcast itself is public and unencrypted.
