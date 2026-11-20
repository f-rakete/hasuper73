"""Parser for SUPER73/Comodule 10-byte metrics frames.

A frame is the 2-byte register ID followed by 8 data bytes, called d2-d9 here
after their position in the frame. The decoders follow the register map the
Comodule backend serves to the official app, the display firmware's own CAN
handler, and reverse.bike's sdcfw for the version registers.
"""

from __future__ import annotations

from .const import (
    BIKE_MODEL_ID,
    BIKE_SERIAL_ID,
    DEFAULT_WHEEL_DIAMETER_M,
    MODULE_VERSIONS_ID,
    MOTION_ID,
    POWER_ID,
    REGION_ID,
    RIDE_ID,
    SETTINGS_ID,
    STATE_OF_CHARGE_ID,
    TOTAL_ID,
    VERSIONS_ID,
    WARNING_ID,
)
from .models import Super73DeviceInfo, Super73State

# The range field is 12 bits; all ones means the bike has no estimate yet.
RANGE_MASK = 0x0FFF
RANGE_UNKNOWN = 0x0FFF

# The warning register carries 14 flag bits per page and the page number in the
# low two bits. The display numbers warnings page * 14 + bit.
WARNINGS_PER_PAGE = 14


def parse_frame(data: bytes, state: Super73State) -> bool:
    """Parse one 10-byte metrics frame into state."""
    if len(data) != 10:
        return False

    register_id = data[:2]
    if register_id == SETTINGS_ID:
        # Walker73 reads walk as d3 == 0, but an S2 reports d3 = 00 with walk
        # mode off, so any non-zero value means walk mode is on.
        state.walk = data[3] != 0x00
        state.light = data[4] == 0x01
        state.assist = data[2]
        state.mode = data[5]
        return True

    if register_id == MOTION_ID:
        state.wheel_speed_kmh = int.from_bytes(data[2:4], "little") / 100
        state.wheel_rpm = _wheel_rpm_from_speed(state.wheel_speed_kmh)
        return True

    if register_id == TOTAL_ID:
        # d6-d9: 32-bit odometer in 0.1 km. Reading only d6-d7 would wrap
        # at 6553.5 km.
        state.total_km = int.from_bytes(data[6:10], "little") / 10
        return True

    if register_id == RIDE_ID:
        state.pedal_rpm = data[3] * 5.0
        raw_range = int.from_bytes(data[8:10], "little") & RANGE_MASK
        if raw_range != RANGE_UNKNOWN:
            state.raw_range = raw_range
            state.range_km = float(raw_range)
        return True

    if register_id == POWER_ID:
        # d2-d5: pack voltage in mV (an S2 reports about 53.9 V when full and
        # sags when the headlight switches on). d6-d9: charge current in mA;
        # it stays at 0 while riding, so it is the charger's current only.
        state.battery_voltage = int.from_bytes(data[2:6], "little") / 1000
        state.charge_current = int.from_bytes(data[6:10], "little") / 1000
        return True

    if register_id == STATE_OF_CHARGE_ID:
        # d2: battery state of charge in %. An all-zero frame is a register
        # the bike hasn't filled, not an empty battery: the bike shuts down
        # long before 0 %.
        if any(data[2:]) and data[2] <= 100:
            state.state_of_charge = data[2]
        return True

    if register_id == WARNING_ID:
        # d8-d9: 16-bit word, page in bits 0-1, warning flags in bits 2-15.
        word = int.from_bytes(data[8:10], "little")
        page = word & 0x03
        flags = word >> 2
        state.warning_codes = tuple(
            page * WARNINGS_PER_PAGE + bit
            for bit in range(WARNINGS_PER_PAGE)
            if flags >> bit & 1
        )
        return True

    return False


def parse_info(frames: dict[bytes, bytes], info: Super73DeviceInfo) -> None:
    """Decode identity and version register frames into device info.

    Only fields whose register was read are changed. A value of 0 means the
    bike doesn't report that unit and is stored as unknown.
    """
    for register_id, frame in frames.items():
        info.raw_frames[register_id.hex()] = frame.hex(" ")

    model = frames.get(BIKE_MODEL_ID)
    if model is not None:
        info.bike_model = _text(model[2:7])

    serial = frames.get(BIKE_SERIAL_ID)
    if serial is not None:
        # The display assembles the serial from ASCII digits: two at the end
        # of the model frame (d8-d9) and eight in the serial frame (d2-d9).
        prefix = model[8:10] if model is not None and model[8:10].isdigit() else b""
        info.bike_serial = _text(prefix + serial[2:10])

    region = frames.get(REGION_ID)
    if region is not None:
        info.region = _text(region[2:6])

    module = frames.get(MODULE_VERSIONS_ID)
    if module is not None:
        info.stm_version = int.from_bytes(module[2:5], "big") or None
        info.controller_variant = (module[5] | module[6] << 8) or None
        info.nrf_bootloader_version = module[7] or None
        info.firmware_variant = module[8] or None

    versions = frames.get(VERSIONS_ID)
    if versions is not None:
        info.controller_version = int.from_bytes(versions[2:6], "big") or None
        info.battery_version = int.from_bytes(versions[6:10], "big") or None


def _text(raw: bytes) -> str | None:
    """Decode a fixed-width ASCII field, or show it as hex if it isn't text."""
    trimmed = raw.strip(b"\x00 ")
    if not trimmed:
        return None
    if all(0x20 <= byte < 0x7F for byte in trimmed):
        return trimmed.decode("ascii")
    return raw.hex(" ")


def _wheel_rpm_from_speed(speed_kmh: float) -> float:
    """Mirror Walker73's wheel RPM calculation."""
    return speed_kmh / DEFAULT_WHEEL_DIAMETER_M / 0.1885
