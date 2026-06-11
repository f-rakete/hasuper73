# Changelog

All notable changes to this project are documented here.

Versions follow semantic versioning. For HACS, every release should keep these
three values aligned:

- `VERSION`
- `custom_components/super73/manifest.json`
- the GitHub release/tag, prefixed with `v`

## 0.1.1 - 2026-06-11

- Add BLE pairing attempt and retry when the bike returns insufficient authentication.
- Bound BLE disconnect during unload so ESPHome Bluetooth proxy disconnect failures do not block Home Assistant reloads.

## 0.1.0 - 2026-06-11

- Initial HACS custom integration.
- Add Bluetooth discovery and manual Bluetooth address setup.
- Add read-only SUPER73/Comodule metrics sensors and binary sensors.
