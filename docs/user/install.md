# Install

Add this repository to Home Assistant's add-on store, install the add-on, pick the controller,
and start it.

## 1. Add the repository

The add-on lives in its own repository:

```text
https://github.com/Yagoor/auracast-addon
```

1. In Home Assistant, open **Settings → Add-ons → Add-on store**.
2. Open the **⋮** menu in the top-right corner and choose **Repositories**.
3. Paste the URL above, select **Add**, and close the dialog.

Or use the My Home Assistant link, which opens the same dialog with the URL filled in:
[Add the repository to my Home Assistant](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2FYagoor%2Fauracast-addon).

```{note}
Newer Home Assistant releases may call add-ons *apps*; the steps are the same.
```

## 2. Install the add-on

The store now lists **Auracast** under the repository's name. Open it and select **Install**.
The image is prebuilt and pulled from `ghcr.io/yagoor/auracast-addon`; nothing is compiled on
your machine.

## 3. Plug in and select the controller

1. Plug the Auracast controller into the Home Assistant machine.
2. Open the add-on's **Configuration** tab.
3. Choose the controller under **Auracast controller**. The list shows the machine's serial
   devices; prefer the `/dev/serial/by-id/…` entry, which keeps pointing at the same controller
   across reboots.
4. Optionally set a **Player name**, then **Save**.

The Supervisor will not start the add-on until a controller is selected. Every option is
described in the [configuration reference](configuration.md).

## 4. Start it

Go back to the **Info** tab and select **Start**. Open the **Log** tab. A healthy start ends
with lines like these:

```text
… INFO [auracast_player.auracast.broadcaster] Broadcasting Auracast with 2 BIS streams
… INFO [auracast_player.sendspin.pairing] No server is paired yet. Pairing token SP:0…
… INFO [auracast_player.sendspin.player] Advertising "Auracast" over mDNS, waiting for Music Assistant
```

Next, [pair Music Assistant with the player](pairing.md).

## Network and devices

The add-on uses the host's network (`host_network: true`): Music Assistant finds it over mDNS and
connects back in to the player on TCP port `8928`. It is given the host's serial devices
(`uart: true`) to reach the controller. No sound card is mapped: the audio goes over the air.

The add-on starts at the `services` stage, before Home Assistant itself, so it is already
advertising when Music Assistant starts looking for players.
