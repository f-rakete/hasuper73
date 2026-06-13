# Changelog

All notable changes to this project are documented here.

Versions follow semantic versioning. For HACS, every release should keep these
three values aligned:

- `VERSION`
- `custom_components/super73/manifest.json`
- the GitHub release/tag, prefixed with `v`

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
