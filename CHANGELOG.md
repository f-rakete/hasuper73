# Changelog

All notable changes to this project are documented here.

Versions follow semantic versioning. For HACS, every release should keep these
three values aligned:

- `VERSION`
- `custom_components/super73/manifest.json`
- the GitHub release/tag, prefixed with `v`

## 0.2.0 - 2026-11-17

- Release the bike between updates. The bike accepts one Bluetooth connection at a time and stops advertising while connected, so the permanent connection locked out the official app and other controllers such as a Puck.js button. Each update now connects, pairs, reads all registers and disconnects again, so the bike is only busy while an update is reading it.
- Treat a bike that is busy with another device, switched off or away as normal: keep the last known values, log at debug level only, and try again on the next update. Connecting, reading and disconnecting each have a time limit, so a missing bike can't stall updates or hold the connection.
- Skip connection attempts while **In range** is off.
- Read every value fresh on each update instead of keeping values from earlier frames, so changes made by other devices (for example the ride mode) show up on the next update.
- **Battery voltage** is now the pack voltage the bike reports (POWER register, bytes d2–d3, in mV) instead of an estimate from the range value. **Limp mode** uses it too.
- Fix **Walk mode**, which was inverted: the bike reports 0 with walk mode off.
- Stop subscribing to notifications and stop reading the undecoded `00 00` register; read device information only once per Home Assistant start. All of this shortens each connection.
- Stop the update timer properly when the integration is unloaded.

## 0.1.4 - 2026-10-29

- Add an "In range" presence binary sensor based on Bluetooth advertisements only, so passive scanners count too and it works without a connection. It turns off after 3 minutes without advertisements, and its `source` and `rssi` attributes show which scanner heard the bike when it came into range.
- Set up the integration even when the bike is off or away. Entities that need a connection stay unavailable until the first successful update.
- Ship English and German translations in `translations/`. Custom integrations do not read `strings.json`, so entity names were missing before: entities without a device class had no name, the others showed Home Assistant's generic device-class name. Existing entity IDs do not change.

## 0.1.3 - 2026-06-13

- Keep the last known bike state when later Bluetooth updates fail, so normal offline periods do not clear entity values.

## 0.1.2 - 2026-06-11

- Add Bluetooth discovery by advertised SUPER73 local name when the bike does not advertise the metrics service UUID.
- Keep post-connect metrics service validation so name-based discovery does not create unsupported entries.

## 0.1.1 - 2026-06-11

- Add BLE pairing attempt and retry when the bike returns insufficient authentication.
- Bound BLE disconnect during unload so ESPHome Bluetooth proxy disconnect failures do not block Home Assistant reloads.

## 0.1.0 - 2026-06-11

- Initial HACS custom integration.
- Add Bluetooth discovery and manual Bluetooth address setup.
- Add read-only SUPER73/Comodule metrics sensors and binary sensors.
