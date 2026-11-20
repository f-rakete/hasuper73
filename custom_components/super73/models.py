"""Models for SUPER73 Bluetooth state."""

from __future__ import annotations

from dataclasses import dataclass, field

from .const import DEFAULT_BASE_MAX_RANGE_KM


@dataclass
class Super73DeviceInfo:
    """Static information: GATT device information plus identity and version registers.

    Read once per Home Assistant run and again each time the bike comes into
    range. A field keeps its last value when a later read fails.
    """

    name: str | None = None
    manufacturer: str | None = None
    software_version: str | None = None
    hardware_version: str | None = None
    firmware_version: str | None = None
    # 0x0210 / 0x0211 / 0x0212
    bike_model: str | None = None
    bike_serial: str | None = None
    region: str | None = None
    # 0xFCFC: display module (nRF bootloader, firmware variant) and CAN bridge
    nrf_bootloader_version: int | None = None
    firmware_variant: int | None = None
    stm_version: int | None = None
    controller_variant: int | None = None
    # 0xFAFA: motor controller and battery management system
    controller_version: int | None = None
    battery_version: int | None = None
    # Register ID (hex) -> frame bytes (hex), for the registers above
    raw_frames: dict[str, str] = field(default_factory=dict)


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
    range_km: float | None = None
    state_of_charge: int | None = None
    battery_voltage: float | None = None
    charge_current: float | None = None
    warning_codes: tuple[int, ...] | None = None
    # Register ID (hex) -> frame bytes (hex), for every register read this update
    raw_frames: dict[str, str] = field(default_factory=dict)
    # Snapshot of the static information at the time of this update
    info: Super73DeviceInfo = field(default_factory=Super73DeviceInfo)

    @property
    def battery_level(self) -> float | None:
        """Return the battery level the bike reports, or estimate it from range.

        The estimate (range against a 60 km full range) is only used when the
        bike doesn't serve its state-of-charge register.
        """
        if self.state_of_charge is not None:
            return float(self.state_of_charge)
        if self.raw_range is None:
            return None
        return min(max(self.raw_range / DEFAULT_BASE_MAX_RANGE_KM, 0.0), 1.0) * 100

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
    def warning(self) -> bool | None:
        """Return whether the controller reports any warning."""
        if self.warning_codes is None:
            return None
        return bool(self.warning_codes)

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
