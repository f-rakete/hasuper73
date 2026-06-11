# SUPER73 Bluetooth for Home Assistant

Read-only HACS custom integration for SUPER73 bikes and other Comodule Diamond
Display vehicles using the Bluetooth protocol documented by Walker73.

## Status

This is an early implementation intended for testing against a real bike. It:

- Discovers bikes exposing the metrics service UUID.
- Allows manual setup by Bluetooth address.
- Subscribes to the metrics notifier.
- Reads the same startup registers as Walker73.
- Exposes read-only sensors and binary sensors.

No write/control entities are exposed.

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
