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
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfLength,
    UnitOfSpeed,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import Super73DataUpdateCoordinator
from .models import Super73State


@dataclass(frozen=True, kw_only=True)
class Super73SensorEntityDescription(SensorEntityDescription):
    """SUPER73 sensor description."""

    value_fn: Callable[[Super73State], int | float | str | None]


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
        key="raw_range",
        translation_key="raw_range",
        entity_registry_enabled_default=False,
        value_fn=lambda state: state.raw_range,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up SUPER73 sensors."""
    coordinator: Super73DataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(Super73Sensor(coordinator, description) for description in SENSORS)


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
