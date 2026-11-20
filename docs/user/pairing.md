# Pairing and listening

Every connection to the player is encrypted, and a server has to pair with it once before it may
play. Then any Auracast receiver can join the broadcast.

## The player appears by itself

Once the add-on is running, Music Assistant discovers it over mDNS. It shows up under the
{ref}`Player name <opt-name>`, with the controller as its device: the manufacturer the controller
reports, a model such as *Bluetooth Core 5.4 controller*, and its firmware revision.

## Pair Music Assistant

Pairing is remembered in the add-on's data, so it survives restarts and updates. There are two
ways to pair.

### With the pairing token

While nothing is paired, the add-on log shows a token once at startup:

```text
No server is paired yet. Pairing token SP:0…
```

Copy the whole `SP:0…` string and paste it into Music Assistant where it asks to pair a player
with a token.

```{warning}
Treat the token like a password: anyone who has it can pair a server with this player. Once a
server is paired the token is no longer logged.
```

### With a 6-digit code

Ask Music Assistant to pair with a code. The player writes the code to its log:

```text
*** Pairing code: 123-456 ***
```

Type it into Music Assistant.

### Skipping pairing

The {ref}`Let unpaired servers play <opt-allow_unpaired>` option lets any server on your network
play without pairing. It is off by default and best left off.

## Listen on Auracast receivers

1. Play something to the player from Music Assistant.
2. On your headphones, speaker or hearing aid, or in its companion app, look for nearby
   broadcasts (often called Auracast or broadcast audio).
3. Pick the {ref}`Broadcast name <opt-broadcast_name>` and join it.

The broadcast is public and unencrypted, so no code is needed to join. It carries 48 kHz stereo
as two streams, front left and front right; a receiver takes the channels it plays.

The broadcast stays up while nothing is playing: the add-on sends silence between streams, so
receivers do not drop off when playback pauses.

## Volume and mute

Volume and mute in Music Assistant change the audio before it is encoded, so they apply to
everyone listening. Each receiver's own volume still works on top. The player remembers its
volume and mute across restarts.
