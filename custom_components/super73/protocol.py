"""Parser for SUPER73/Comodule 10-byte metrics frames."""

from __future__ import annotations

from .const import (
    DEFAULT_BASE_MAX_RANGE_KM,
    DEFAULT_REAL_MAX_RANGE_KM,
    DEFAULT_WHEEL_DIAMETER_M,
    MOTION_ID,
    POWER_ID,
    RIDE_ID,
    SETTINGS_ID,
    TOTAL_ID,
)
from .models import Super73State


def parse_frame(data: bytes, state: Super73State) -> bool:
    """Parse one Walker73-compatible 10-byte metrics frame into state."""
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
        state.total_km = int.from_bytes(data[6:8], "little") / 10
        return True

    if register_id == RIDE_ID:
        state.pedal_rpm = data[3] * 5.0
        state.raw_range = data[8]
        state.range_km = _range_from_raw(state.raw_range)
        state.battery_level = _battery_level_from_raw(state.raw_range)
        return True

    if register_id == POWER_ID:
        # d2-d3: pack voltage in mV (an S2 reports about 53.9 V when full and
        # sags when the headlight switches on). d6-d7: charge current in mA.
        state.battery_voltage = int.from_bytes(data[2:4], "little") / 1000
        state.charge_current = int.from_bytes(data[6:8], "little") / 1000
        return True

    return False


def _wheel_rpm_from_speed(speed_kmh: float) -> float:
    """Mirror Walker73's wheel RPM calculation."""
    return speed_kmh / DEFAULT_WHEEL_DIAMETER_M / 0.1885


def _range_from_raw(raw_range: int) -> float:
    """Convert the raw range byte into km."""
    clamped = min(max(float(raw_range), 0.0), DEFAULT_BASE_MAX_RANGE_KM)
    return (clamped / DEFAULT_BASE_MAX_RANGE_KM) * DEFAULT_REAL_MAX_RANGE_KM


def _battery_level_from_raw(raw_range: int) -> float:
    """Convert the raw range byte into a 0-100 percentage."""
    return min(max(raw_range / DEFAULT_BASE_MAX_RANGE_KM, 0.0), 1.0) * 100
