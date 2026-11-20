"""Scratch checks for hasuper73's decoders and entity wiring (needs homeassistant installed; run with python tests/test_super73.py)."""

import json
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from custom_components.super73 import binary_sensor, sensor  # noqa: E402
from custom_components.super73.models import Super73DeviceInfo, Super73State  # noqa: E402
from custom_components.super73.protocol import parse_frame, parse_info  # noqa: E402


def frame(text: str) -> bytes:
    data = bytes.fromhex(text)
    assert len(data) == 10, text
    return data


def parsed(*frames: str) -> Super73State:
    state = Super73State()
    for text in frames:
        assert parse_frame(frame(text), state), text
    return state


# POWER: 53.93 V, the value super73-puck read off the S2; no charger.
s = parsed("04 01 aa d2 00 00 00 00 00 00")
assert s.battery_voltage == 53.93 and s.charge_current == 0.0, s
assert s.charging is False and s.limp is False

s = parsed("04 01 aa d2 00 00 d0 07 00 00")
assert s.charge_current == 2.0 and s.charging is True

# Charge current is signed: real S2 frames (2026-11-18) with ff ff in d8-d9.
s = parsed("04 01 f1 c2 00 00 45 fe ff ff")
assert s.charge_current == -0.443 and s.charging is False, s.charge_current
s = parsed("04 01 30 cb 00 00 8f ca ff ff")
assert s.charge_current == -13.681 and s.charging is False, s.charge_current

# TOTAL: 7000.0 km needs all four bytes (d6-d7 alone would read 446.4 km).
s = parsed("02 02 00 24 00 00 70 11 01 00")
assert s.total_km == 7000.0, s.total_km

# RIDE: 12-bit range, upper nibble of d9 ignored, 0xFFF = no estimate.
s = parsed("02 03 00 0c 00 00 00 00 2c f1")
assert s.range_km == 300.0 and s.raw_range == 300 and s.pedal_rpm == 60.0, s
s = parsed("02 03 00 00 00 00 00 00 ff 0f")
assert s.range_km is None and s.raw_range is None

# Battery: the SoC register wins over the range estimate.
s = parsed("02 03 00 00 00 00 00 00 1e 00", "04 02 55 00 00 00 00 00 00 00")
assert s.state_of_charge == 85 and s.battery_level == 85.0
# An all-zero SoC frame is an unfilled register: fall back to range (30/60 km).
s = parsed("02 03 00 00 00 00 00 00 1e 00", "04 02 00 00 00 00 00 00 00 00")
assert s.state_of_charge is None and s.battery_level == 50.0
s = parsed("04 02 00 00 00 00 00 00 00 00")
assert s.battery_level is None

# WARNING: page 1, flag bits 0 and 3 -> codes 14 and 17.
s = parsed("02 00 00 00 00 00 00 00 25 00")
assert s.warning_codes == (14, 17) and s.warning is True, s.warning_codes
s = parsed("02 00 00 00 00 00 00 00 00 00")
assert s.warning_codes == () and s.warning is False

# SETTINGS: unchanged behaviour.
s = parsed("03 00 04 00 01 07 00 00 00 00")
assert (s.assist, s.walk, s.light, s.mode, s.mode_name) == (4, False, True, 7, "EU OFF-ROAD")

# Unknown register IDs are ignored.
assert parse_frame(frame("00 00 01 04 07 00 00 00 00 00"), Super73State()) is False

# Identity + versions.
info = Super73DeviceInfo()
parse_info(
    {
        bytes.fromhex("0210"): frame("02 10 52 58 20 20 20 00 31 32"),
        bytes.fromhex("0211"): frame("02 11 33 34 35 36 37 38 39 30"),
        bytes.fromhex("0212"): frame("02 12 45 55 00 00 00 00 00 00"),
        bytes.fromhex("fcfc"): frame("fc fc 03 11 37 00 00 06 e7 00"),
        bytes.fromhex("fafa"): frame("fa fa 00 00 01 9a 00 00 00 00"),
    },
    info,
)
assert info.bike_model == "RX", info.bike_model
assert info.region == "EU"
assert info.stm_version == 201015 and info.controller_variant is None
assert info.nrf_bootloader_version == 6 and info.firmware_variant == 231
assert info.controller_version == 410 and info.battery_version is None
assert info.raw_frames["fafa"] == "fa fa 00 00 01 9a 00 00 00 00"

# Non-text bytes show as hex rather than garbage.
info = Super73DeviceInfo(controller_version=430)
parse_info(
    {
        bytes.fromhex("0210"): frame("02 10 01 02 03 04 05 00 ff ff"),
        bytes.fromhex("0211"): frame("02 11 41 42 00 00 00 00 00 00"),
    },
    info,
)
assert info.bike_model == "01 02 03 04 05", info
assert info.controller_version == 430, "an unread register keeps its last value"

# Entities: every value_fn runs on an empty and a full state; every
# translation key exists in both languages.
full = parsed(
    "04 01 aa d2 00 00 00 00 00 00",
    "02 02 00 24 00 00 70 11 01 00",
    "02 03 00 0c 00 00 00 00 2c 01",
    "04 02 55 00 00 00 00 00 00 00",
    "02 00 00 00 00 00 00 00 25 00",
    "03 00 04 00 01 07 00 00 00 00",
    "02 01 c4 09 00 00 00 00 00 00",
)
full.raw_frames["0401"] = "04 01 aa d2 00 00 00 00 00 00"
full.info = Super73DeviceInfo(controller_version=410, raw_frames={"fafa": "fa fa"})
values = {}
for description in (*sensor.SENSORS, *sensor.RAW_FRAME_SENSORS):
    description.value_fn(Super73State())
    values[description.key] = description.value_fn(full)
for description in binary_sensor.BINARY_SENSORS:
    description.value_fn(Super73State())
    values[description.key] = description.value_fn(full)
    if description.attrs_fn:
        description.attrs_fn(Super73State())
assert values["battery"] == 85.0 and values["speed"] == 25.0
assert values["warning_codes"] == "14, 17" and values["warning"] is True
assert values["controller_firmware"] == 410
assert values["raw_0401"].startswith("04 01") and values["raw_fafa"] == "fa fa"
assert values["raw_0402"] is None
assert sensor._warning_codes(parsed("02 00 00 00 00 00 00 00 00 00")) == "none"

keys = {d.key for d in sensor.SENSORS}
assert len(keys) == len(sensor.SENSORS)
raw_keys = [d.key for d in sensor.RAW_FRAME_SENSORS]
assert raw_keys == [
    "raw_0300", "raw_0202", "raw_0203", "raw_0401", "raw_0201",
    "raw_0402", "raw_0200", "raw_0210", "raw_0211", "raw_0212",
    "raw_fcfc", "raw_fafa",
], raw_keys
assert sensor.RAW_FRAME_SENSORS[0].translation_placeholders == {"register": "0300"}

base = REPO / "custom_components" / "super73"
for path in (base / "strings.json", base / "translations/en.json", base / "translations/de.json"):
    entity = json.loads(path.read_text(encoding="utf-8"))["entity"]
    sensor_keys = {d.translation_key for d in (*sensor.SENSORS, *sensor.RAW_FRAME_SENSORS)}
    sensor_keys |= {"module_id"}
    missing = sensor_keys - set(entity["sensor"])
    binary_keys = {d.translation_key for d in binary_sensor.BINARY_SENSORS} | {"in_range"}
    missing |= binary_keys - set(entity["binary_sensor"])
    assert not missing, (path.name, missing)
    assert "{register}" in entity["sensor"]["raw_frame"]["name"], path.name

print("all checks passed")
