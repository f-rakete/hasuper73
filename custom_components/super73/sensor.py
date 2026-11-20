"""Sensors for SUPER73 Bluetooth."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfLength,
    UnitOfSpeed,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    INFO_REGISTER_IDS,
    OPTIONAL_REGISTER_IDS,
    REGISTER_IDS,
    VERSION_REGISTER_IDS,
)
from .coordinator import Super73DataUpdateCoordinator
from .models import Super73State


@dataclass(frozen=True, kw_only=True)
class Super73SensorEntityDescription(SensorEntityDescription):
    """SUPER73 sensor description."""

    value_fn: Callable[[Super73State], int | float | str | None]


def _warning_codes(state: Super73State) -> str | None:
    """Return the active warning codes as text."""
    if state.warning_codes is None:
        return None
    return ", ".join(str(code) for code in state.warning_codes) or "none"


SENSORS: tuple[Super73SensorEntityDescription, ...] = (
    Super73SensorEntityDescription(
        key="battery",
        translation_key="battery",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda state: state.battery_level,
    ),
    Super73SensorEntityDescription(
        key="range",
        translation_key="range",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda state: state.range_km,
    ),
    Super73SensorEntityDescription(
        key="speed",
        translation_key="speed",
        device_class=SensorDeviceClass.SPEED,
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda state: state.wheel_speed_kmh,
    ),
    Super73SensorEntityDescription(
        key="odometer",
        translation_key="odometer",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=1,
        value_fn=lambda state: state.total_km,
    ),
    Super73SensorEntityDescription(
        key="wheel_rpm",
        translation_key="wheel_rpm",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda state: state.wheel_rpm,
    ),
    Super73SensorEntityDescription(
        key="pedal_rpm",
        translation_key="pedal_rpm",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda state: state.pedal_rpm,
    ),
    Super73SensorEntityDescription(
        key="battery_voltage",
        translation_key="battery_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda state: state.battery_voltage,
    ),
    Super73SensorEntityDescription(
        key="charge_current",
        translation_key="charge_current",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda state: state.charge_current,
    ),
    Super73SensorEntityDescription(
        key="assist",
        translation_key="assist",
        value_fn=lambda state: state.assist,
    ),
    Super73SensorEntityDescription(
        key="mode",
        translation_key="mode",
        value_fn=lambda state: state.mode,
    ),
    Super73SensorEntityDescription(
        key="mode_name",
        translation_key="mode_name",
        value_fn=lambda state: state.mode_name,
    ),
    Super73SensorEntityDescription(
        key="warning_codes",
        translation_key="warning_codes",
        value_fn=_warning_codes,
    ),
    Super73SensorEntityDescription(
        key="raw_range",
        translation_key="raw_range",
        entity_registry_enabled_default=False,
        value_fn=lambda state: state.raw_range,
    ),
    # Identity and versions, read once, on the first connection after Home
    # Assistant starts.
    Super73SensorEntityDescription(
        key="bike_model",
        translation_key="bike_model",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda state: state.info.bike_model,
    ),
    Super73SensorEntityDescription(
        key="region",
        translation_key="region",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda state: state.info.region,
    ),
    Super73SensorEntityDescription(
        key="display_firmware",
        translation_key="display_firmware",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda state: state.info.firmware_version
        or state.info.software_version,
    ),
    Super73SensorEntityDescription(
        key="display_hardware",
        translation_key="display_hardware",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda state: state.info.hardware_version,
    ),
    Super73SensorEntityDescription(
        key="display_bootloader",
        translation_key="display_bootloader",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda state: state.info.nrf_bootloader_version,
    ),
    Super73SensorEntityDescription(
        key="firmware_variant",
        translation_key="firmware_variant",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda state: state.info.firmware_variant,
    ),
    Super73SensorEntityDescription(
        key="can_bridge_firmware",
        translation_key="can_bridge_firmware",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda state: state.info.stm_version,
    ),
    Super73SensorEntityDescription(
        key="controller_firmware",
        translation_key="controller_firmware",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda state: state.info.controller_version,
    ),
    Super73SensorEntityDescription(
        key="controller_variant",
        translation_key="controller_variant",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda state: state.info.controller_variant,
    ),
    Super73SensorEntityDescription(
        key="battery_firmware",
        translation_key="battery_firmware",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda state: state.info.battery_version,
    ),
)


def _raw_frame_description(register_id: bytes) -> Super73SensorEntityDescription:
    """Describe the disabled-by-default sensor showing one register's raw frame."""
    key = register_id.hex()
    return Super73SensorEntityDescription(
        key=f"raw_{key}",
        translation_key="raw_frame",
        translation_placeholders={"register": key.upper()},
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda state: state.raw_frames.get(key)
        or state.info.raw_frames.get(key),
    )


RAW_FRAME_SENSORS: tuple[Super73SensorEntityDescription, ...] = tuple(
    _raw_frame_description(register_id)
    for register_id in (
        *REGISTER_IDS,
        *OPTIONAL_REGISTER_IDS,
        *INFO_REGISTER_IDS,
        *VERSION_REGISTER_IDS,
    )
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up SUPER73 sensors."""
    coordinator: Super73DataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            *(
                Super73Sensor(coordinator, description)
                for description in (*SENSORS, *RAW_FRAME_SENSORS)
            ),
            Super73ModuleIdSensor(coordinator),
        ]
    )


class Super73Sensor(CoordinatorEntity[Super73DataUpdateCoordinator], SensorEntity):
    """SUPER73 sensor."""

    entity_description: Super73SensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: Super73DataUpdateCoordinator,
        description: Super73SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.address}_{description.key}"
        self._attr_device_info = coordinator.device_info

    @property
    def native_value(self) -> int | float | str | None:
        """Return the sensor value."""
        return self.entity_description.value_fn(self.coordinator.data)


class Super73ModuleIdSensor(SensorEntity):
    """The Comodule module ID the bike advertises.

    Comes from advertisements, so it is known without a connection.
    """

    _attr_has_entity_name = True
    _attr_translation_key = "module_id"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_should_poll = False

    def __init__(self, coordinator: Super73DataUpdateCoordinator) -> None:
        """Initialize the sensor."""
        self._presence = coordinator.presence
        self._attr_unique_id = f"{coordinator.address}_module_id"
        self._attr_device_info = coordinator.device_info

    async def async_added_to_hass(self) -> None:
        """Subscribe to presence changes, which include module ID changes."""
        self.async_on_remove(
            self._presence.async_add_listener(self.async_write_ha_state)
        )

    @property
    def native_value(self) -> str | None:
        """Return the advertised module ID."""
        return self._presence.module_id
