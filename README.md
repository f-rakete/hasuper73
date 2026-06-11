# SUPER73 Bluetooth for Home Assistant

Read-only HACS custom integration for SUPER73 bikes and other Comodule Diamond
Display vehicles using the Bluetooth protocol documented by Walker73.

## Status

Current version: `0.1.1`

This is an early implementation intended for testing against a real bike. It:

- Discovers bikes exposing the metrics service UUID.
- Allows manual setup by Bluetooth address.
- Subscribes to the metrics notifier.
- Reads the same startup registers as Walker73.
- Exposes read-only sensors and binary sensors.

No write/control entities are exposed.

## HACS install

Add this repository to HACS as a custom repository:

- Category: Integration
- Repository URL: `https://github.com/f-rakete/hasuper73`

Install the integration, restart Home Assistant, then add **SUPER73 Bluetooth**
from **Settings > Devices & services**.

## Entities

- Battery
- Range
- Speed
- Odometer
- Wheel RPM
- Pedal RPM
- Battery voltage
- Charge current
- Assist
- Mode
- Mode name
- Light
- Walk mode
- Charging
- Limp mode

## Debug logging

Add this to `configuration.yaml` while testing:

```yaml
logger:
  logs:
    custom_components.super73: debug
```

## Attribution

The BLE UUIDs, register IDs, polling order, and frame decoding are based on
[Walker73](https://github.com/f-rakete/Walker73).

## Releasing

HACS reads the integration version from
`custom_components/super73/manifest.json`. Release versions should also be
recorded in `VERSION` and `CHANGELOG.md`.

Release checklist:

1. Update `VERSION`.
2. Update `custom_components/super73/manifest.json`.
3. Add a `CHANGELOG.md` entry.
4. Commit the changes.
5. Create and push a matching tag, for example `v0.1.1`.
6. Create a GitHub release from that tag.
