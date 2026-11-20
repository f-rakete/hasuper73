# Handover: hasuper73 0.3.0, every BLE value as a Home Assistant sensor

You have direct access to Flo's Home Assistant. Your job is to install this
branch, check it against the real bike, fix what the live data contradicts, and
then release it. The code was written and tested on a machine with **no
Bluetooth and no HA instance**, so nothing here has run against the bike yet.

- Repo: `https://github.com/f-rakete/hasuper73`
- Branch: **`feature/all-ble-sensors`** (one commit on top of `main` = v0.2.0)
- Not merged, not tagged, not released. HACS users stay on v0.2.0.
- Bike: SUPER73 S2, BLE address `F5:14:76:B9:41:BA` (random static), advertised
  name `SUPER73`, display firmware `221122`, hardware `v3.2.0`.

## Goal

The user wants **all info the bike exposes over Bluetooth to show up as sensors
in HA**, including the controller version and the other firmware versions.

## What the branch adds

Every update (each 10 s; connect → pair → read → disconnect, as v0.2.0) now
reads two more registers. Identity and versions are read once, on the first
connection after HA starts, in a separate step with its own 8 s limit that can
never fail an update. A failure is not retried until the next HA start
(changed 2026-11-20 after the bike test, see below).

| Entity | Source | Decode | Confidence |
|---|---|---|---|
| Battery (now real) | reg `04 02` d2 | % (all-zero frame = unfilled → falls back to the old range/60 km estimate) | high: backend config + display's `<6 %` low-battery check |
| Warning (binary, problem) + Warning codes | reg `02 00` d8–d9 | u16 LE: page = bits 0–1, flags = bits 2–15, code = page×14 + bit | medium: display iterates these bits into a warning function; meaning of codes unknown |
| Odometer (fixed) | `02 02` d6–d9 | u32 LE ×0.1 km (was u16, would wrap at 6553.5 km) | high |
| Range (fixed) | `02 03` d8–d9 | u16 LE & 0x0FFF km, 0xFFF = unknown; no 60 km cap | high |
| Battery voltage / Charge current | `04 01` d2–d5 / d6–d9 | u32 LE mV / mA (was u16) | high |
| Bike model | `02 10` d2–d6 | ASCII (hex if not printable) | medium |
| ~~Bike serial number~~ | `02 11` | removed 2026-11-20: on the S2 it holds four non-ASCII bytes that match no reading of the stamped frame number | only the raw-frame sensor remains |
| Region | `02 12` d2–d5 | ASCII, expect `EU` | high |
| CAN bridge firmware | `FC FC` d2–d4 | u24 BE, expect **201015** | high (sdcfw) |
| Firmware type (key `controller_variant`) | `FC FC` d5–d6 | d5 \| d6<<8, 0 → unknown | **verified**: 231 on the S2, = the app's "Firmware type" |
| Display bootloader | `FC FC` d7 | expect 6 | high (sdcfw) |
| Firmware variant | `FC FC` d8 | maybe 231 (= firmwareType)? unverified | high (sdcfw) |
| Controller firmware | `FA FA` d2–d5 | u32 BE, expect **410** (stock S2) or 430 | high (sdcfw) |
| Battery firmware | `FA FA` d6–d9 | u32 BE, 0 → unknown | high (sdcfw) |
| Display firmware / hardware | DIS `2a26` (fallback `2a28`) / `2a27` | text | high |
| Module ID | advertised manufacturer data `0x020F`, first 8 bytes | hex, expect **`1133a890eabfe9ba`** | high |
| Raw register XXXX (12 sensors, disabled by default) | every register read | full frame in hex | n/a |

Versions and the module ID are also pushed to the device page
(`sw_version`, `hw_version`, `serial_number`).

**Authentication for `FC FC` / `FA FA`:** the integration first reads them
plainly. Only if the bike doesn't answer with a matching frame does it answer
the security service once, as sdcfw and the official app do: read the challenge
`2556`, write `SHA-1(challenge ‖ 20×0xFF)` to `2557`, read `2558` (non-zero =
ok). A wrong answer makes the display disconnect, so a failure sets
`_auth_failed` and is not retried until HA restarts.

**Why these decodes:** a BLE register frame is the controller's CAN frame
passed through (`[id_hi id_lo d0..d7]`, BLE d(n+2) = CAN d(n)). Sources: the
Comodule backend register config (`super73-fw/work/firmware/vendor/config-231.json`,
documented in `super73-fw/docs/backend-config-register-map.md`), the display
firmware's CAN handler (`super73-fw/docs/can-protocol.md`), and reverse.bike
sdcfw `packages/ble-utils/info.ts` + `auth.ts` for the version registers.

## Files

- `custom_components/super73/protocol.py`: all decoders (`parse_frame`,
  `parse_info`). Fix decode mistakes here.
- `custom_components/super73/client.py`: session flow. `_read_session` (core
  plus optional registers), `_read_info_session` / `_read_info_registers` /
  `_authenticate`, and `_read_optional_register`, which needs an echoed
  register ID and never re-pairs. Optional registers the bike didn't answer
  are skipped until it next comes into range (`_unserved`).
- `custom_components/super73/const.py`: register lists (`REGISTER_IDS` core,
  `OPTIONAL_REGISTER_IDS`, `INFO_REGISTER_IDS`, `VERSION_REGISTER_IDS`) and
  timeouts.
- `coordinator.py`: re-read info on in-range, device registry sync.
  `presence.py`: module ID. `sensor.py` / `binary_sensor.py`: entities.
  Translations: en/de plus `strings.json` (identical to `en.json`).
- `tests/test_super73.py` (decoders + entity wiring + translation keys) and
  `tests/test_client.py` (fake bike: auth fallback, auth rejection with
  disconnect, unsupported registers, retry pause, core failure). Both need
  `homeassistant` importable; run them as `python tests/test_super73.py`. They
  passed against HA 2026.2.3 (the newest for Python 3.13). They are scratch
  checks, not pytest.

## What to do

1. **Install the branch on HA.** Clone it and copy `custom_components/super73`
   over `/config/custom_components/super73`, or use HACS → hasuper73 →
   Redownload if it offers the branch. Restart HA.
2. **Debug logging:**
   ```yaml
   logger:
     logs:
       custom_components.super73: debug
   ```
3. **Switch the bike on near a proxy.** Then collect these from the log:
   - `SUPER73 frame: …` lines for every register;
   - `register XXXX not served (got …)` / `not readable`, which tells you
     which registers this bike doesn't serve;
   - whether `SUPER73 authenticated` appears, or `rejected authentication`;
   - `device information read in X s` and `link released after X s`.
4. **Enable the Raw register sensors** and compare each decoded value against
   the official app (Bike passport shows STM 201015, nRF 221122,
   firmwareType 231 and the module ID) and against the bike itself:
   - Battery % vs the app;
   - Odometer vs the app;
   - Range vs the app;
   - Controller firmware should be 410 or 430; CAN bridge 201015;
     bootloader 6;
   - Module ID `1133a890eabfe9ba`;
   - Region `EU`;
   - Bike model / serial: whatever is readable. If the serial looks wrong,
     try the backend's u32 LE reading of `02 11` d2–d5.
5. **Settle the uncertain decodes** in `protocol.py` using the raw frames. In
   particular:
   - the serial format;
   - whether `04 02` is really served over BLE on the S2;
   - whether `02 00` is served and what a real warning looks like. A warning
     can be provoked safely, for example by unplugging the throttle or a light
     connector with the bike off;
   - `FC FC` d8 (firmware variant).

   Not decoded yet, so they appear only in raw frames: `02 02` d2–d5 (d3 was
   seen flicking `4E`/`4D` while the motor runs, `24` at rest) and `02 03` d2
   and d4–d7. Not read at all (each would add a read to every update):
   `04 00` status word, `04 03`, `02 66` (backend calls it "mcu version" but
   decodes it differently from the display), `04 66`.
6. **Check the Puck still works.** The Puck.js button (`super73-puck`) needs
   the bike free, and the info step makes one connection per ride a few seconds
   longer. Press the Puck right after switching the bike on; it should still
   switch the mode within ~3 s.
7. **Check the auth path is harmless.** It must not disconnect the bike
   repeatedly, and the official app must still connect afterwards.
8. **Release when it works on the bike.** Merge to `main`, keep
   `VERSION` / `manifest.json` / `CHANGELOG.md` at 0.3.0 (or bump and amend the
   changelog to match what changed), tag `v0.3.0`, create the GitHub release
   (see the README release checklist).

## Verified on the bike (2026-11-20, HA 2026.11.1, via ESPHome proxy)

- Module ID `1133a890eabfe9ba`, CAN bridge 201015, display 221122 / v3.2.0,
  firmware type 231: all match the official app's Bike passport. Bootloader 6,
  controller firmware 430, battery firmware 105, model `S73RX`.
- `FC FC` / `FA FA` answer without authentication; the security challenge
  never ran.
- `04 02` is served (100 % at the end of a charge; 0.1.x also received it as
  notifications, 58→87 % while charging).
- Not served by the S2: `02 00` (warnings), `02 12` (region). `FC FC` d8
  reads 0.
- Odometer, range and voltage: the extra bytes the wider decodes read were 0
  in all 56,745 frames logged 2026-11-06…20, so values are unchanged.
- Charge current is **signed** (frames with `ff ff` in d8–d9 = small negative
  currents, e.g. −0.443 A); fixed.
- Sessions degraded within minutes on the first test (hung reads, 18–25 s
  holds, failed connects), where 0.2.0 typically held the bike 1.4 s. The
  repeated reads of the unserved `02 00` plus a direct read of the notifier
  characteristic were the main difference, so both are gone now.
- With those gone, the info read hung (15 s) on the next try and every connect
  failed for minutes afterwards, although the bike kept advertising. Both bad
  runs started right after the info read, so it is now done once per HA start
  with an 8 s limit, and each info read is logged before it starts
  (`SUPER73 reading register XXXX` / `reading characteristic XXXX`) to find
  the register that hangs.

## Known issues and notes

- `presence.py` (already in v0.1.4+) calls
  `bluetooth.async_register_advertisement_callback`. It **exists in HA
  2026.11.2** (checked in the source) but **not in 2026.2.3**, so the
  integration has an undeclared minimum HA version. Consider adding
  `"homeassistant": "<first version with it>"` to `hacs.json`.
- Charge current is charger-only (confirmed 2026-11-20: ~0 A at full throttle).
  There is no load-current telemetry over BLE.
- The integration is read-only by design. Never write to `REGISTER` (`155f`)
  or to the DFU characteristic.
- Mode 4 (EU EPAC) is the only road-legal mode in Austria; this integration
  never changes the mode.
- Deeper context (firmware RE, CAN map, OTA API) lives in the separate repo
  `f-rakete/super73-fw` (`HANDOFF.md`, `FINDINGS.md`, `docs/`). Work there goes
  straight to its `main`; hasuper73 work goes on feature branches.
