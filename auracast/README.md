# Auracast

Turns a Bluetooth LE Audio controller on the machine running Home Assistant into a Music
Assistant player that broadcasts over [Auracast](https://www.bluetooth.com/auracast/). Anyone
with an Auracast receiver in range, such as headphones, a speaker or a hearing aid, can join the
broadcast.

The player is [Sendspin](https://sendspin-audio.com), the playback protocol built into Music
Assistant, so it shows up in Music Assistant by itself and needs nothing enabled there.

## What you need

- A Music Assistant whose Sendspin support is built on aiosendspin 10 or later.
- A Bluetooth LE Audio controller flashed for Auracast, connected to this machine. An ordinary
  Bluetooth dongle, or the computer's built-in Bluetooth, will not work.
- Music Assistant and this player on the same local network.

## Getting started

1. Plug in the controller, then install and open this app's **Configuration** tab.
2. Choose the controller under **Auracast controller**, then start the app.
3. In Music Assistant the player appears by itself, named after **Player name**.
4. Pair Music Assistant with the player, see below, and play something to it.
5. On your headphones or speaker, look for the broadcast name and join it.

## Pairing with Music Assistant

Every connection to the player is encrypted, and a server has to **pair** with it once before
it may play. Pairing is remembered in this app's data, so it survives restarts and updates.

- **The pairing token.** While nothing is paired, the log shows it once at startup, on a line
  that starts `No server is paired yet. Pairing token`. Paste the `SP:0...` string into Music
  Assistant where it asks to pair a player with a token.
- **A 6-digit code.** Ask Music Assistant to pair with a code. The player logs it as
  `*** Pairing code: 123-456 ***`; type it into Music Assistant.

Treat the token like a password: anyone who has it can pair a server with this player.

## Known limits

- Receivers join the broadcast themselves. Music Assistant does not see or control them.
- This player does not yet line its audio up with other Sendspin players, so do not group it
  with players you listen to in the same room.
- One controller carries one broadcast.
