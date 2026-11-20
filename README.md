# SUPER73 Bluetooth for Home Assistant

<p align="center">
  <img src="assets/icon.png" alt="SUPER73 Bluetooth" width="160">
</p>

Read-only HACS custom integration for SUPER73 bikes and other Comodule Diamond
Display vehicles using the Bluetooth protocol documented by Walker73.

## Status

Current version: `0.3.0`

This is an early implementation intended for testing against a real bike. It:

- Discovers bikes exposing the metrics service UUID.
- Discovers likely SUPER73 bikes by advertised Bluetooth name.
- Allows manual setup by Bluetooth address.
- Connects every 10 seconds, reads the live registers, and disconnects again.
- Reads the bike's identity and firmware versions once per Home Assistant
  start and again each time the bike comes into range.
- Exposes read-only sensors and binary sensors.

No write/control entities are exposed. The integration never changes the ride
mode, assist or light.

## Bluetooth connection

The bike accepts one Bluetooth connection at a time and stops advertising while
something is connected. So the integration doesn't keep a connection open: each
update connects, pairs (Just Works, or re-encrypts with the stored bond), reads,
and disconnects. The bike is only busy while an update is reading it and is
free for the official app or another controller the rest of the time.

If the bike is busy with another device, switched off, or away, the update is
skipped quietly (debug log only) and the entities keep their last values. The
next update tries again. Entities only become available after the first
successful update since Home Assistant started.

## HACS install

Add this repository to HACS as a custom repository:

- Category: Integration
- Repository URL: `https://github.com/f-rakete/hasuper73`

Install the integration, restart Home Assistant, then add **SUPER73 Bluetooth**
from **Settings > Devices & services**.

The repository icon is included at `assets/icon.png`. Home Assistant's
integration tile branding is controlled by the Home Assistant Brands repository.

## Entities

Ride data, read on every update:

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
- Warning codes
- Light
- Walk mode
- Charging
- Limp mode
- Warning
- In range

Diagnostic, read once per Home Assistant start and each time the bike comes
into range:

- Bike model, Bike serial number, Region
- Display firmware, Display hardware, Display bootloader, Firmware variant
- CAN bridge firmware
- Controller firmware, Controller variant
- Battery firmware
- Module ID (from the bike's advertisements, so known without connecting)

Also diagnostic, but disabled by default: a **Raw register** sensor for every
register the integration reads, showing the whole frame in hex. They are meant
for working out the bytes that aren't decoded yet; enable the ones you need.
Their values come from reads that happen anyway, so they don't lengthen the
connection.

**In range** only listens to Bluetooth advertisements and never connects, so
any scanner counts, including passive ones such as Shelly devices. It turns on
with the first advertisement and off after 3 minutes without one. The bike
switches itself off after 5 minutes idle, so a fresh "on" usually means it was
just switched on, for example on arrival. The `source` and `rssi` attributes
show which scanner heard it when it came into range. While **In range** is off,
the integration doesn't try to connect.

**Battery** is the state of charge the bike reports. If a bike doesn't serve
that register, it falls back to an estimate from the range value against a
60 km full range. **Range** is the bike's own estimate in km. **Battery
voltage** is the pack voltage the bike reports. **Charge current** is the
charger's current only; it stays at 0 while riding.

**Warning** turns on while the controller reports a warning. The **Warning
codes** sensor and the warning's `codes` attribute list the active codes as the
display numbers them internally (page × 14 + bit). What each code means is not
known yet.

The version sensors come from two registers that reverse.bike's
[sdcfw](https://github.com/reverse-bike/sdcfw) reads before a controller
update. The integration reads them without authenticating first. Only if the
bike doesn't answer does it answer the bike's security challenge the way the
official app does. If the bike rejects that, the integration doesn't try again
until Home Assistant restarts, and the version sensors stay unknown. A version
the bike reports as 0 (for example a battery that doesn't report its firmware)
shows as unknown.

## Debug logging

Add this to `configuration.yaml` while testing:

```yaml
logger:
  logs:
    custom_components.super73: debug
```

## Attribution

The BLE UUIDs, register IDs, polling order, and frame decoding are based on
[Walker73](https://github.com/AxelFougues/Walker73). The version registers and
the security-service handshake follow reverse.bike's
[sdcfw](https://github.com/reverse-bike/sdcfw).

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
