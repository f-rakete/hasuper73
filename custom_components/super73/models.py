"""Models for SUPER73 Bluetooth state."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Super73DeviceInfo:
    """Static device information read from GATT."""

    name: str | None = None
    manufacturer: str | None = None
    software_version: str | None = None
    hardware_version: str | None = None


@dataclass
class Super73State:
    """Decoded state from the bike metrics registers."""

    metric: bool = True
    mode: int | None = None
    assist: int | None = None
    walk: bool | None = None
    light: bool | None = None
    wheel_speed_kmh: float | None = None
    wheel_rpm: float | None = None
    total_km: float | None = None
    pedal_rpm: float | None = None
    raw_range: int | None = None
    battery_level: float | None = None
    battery_voltage: float | None = None
    charge_current: float | None = None
    range_km: float | None = None

    @property
    def charging(self) -> bool | None:
        """Return whether the bike appears to be charging."""
        if self.charge_current is None:
            return None
        return self.charge_current >= 2.0

    @property
    def limp(self) -> bool | None:
        """Return whether Walker73 would mark limp mode."""
        if self.battery_voltage is None:
            return None
        return self.battery_voltage < 41.0

    @property
    def mode_name(self) -> str | None:
        """Return the Walker73 mode descriptor."""
        if self.mode is None or self.mode >= len(MODE_NAMES):
            return None
        return MODE_NAMES[self.mode]


MODE_NAMES: tuple[str, ...] = (
    "US CLASS1",
    "US CLASS2",
    "US CLASS3",
    "US OFF-ROAD",
    "EU EPAC",
    "EU MID",
    "EU HIGH",
    "EU OFF-ROAD",
)
