# Changelog

## 0.1.2

- The app runs under its own AppArmor profile, which limits it to the controller, its own data
  and the network, and raises its security rating from 4 to 5.

## 0.1.1

- The app only starts with a supported Auracast controller (USB ID 2FE3:0004), and says which
  port it refused and why, instead of failing later while opening it.
- The app has the Auracast icon and logo in the add-on store.

## 0.1.0

- First version: a Sendspin player that broadcasts what it receives over Auracast.
