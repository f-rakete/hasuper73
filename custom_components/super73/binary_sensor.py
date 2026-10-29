"""Binary sensors for SUPER73 Bluetooth."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import Super73DataUpdateCoordinator
from .models import Super73State


@dataclass(frozen=True, kw_only=True)
class Super73BinarySensorEntityDescription(BinarySensorEntityDescription):
    """SUPER73 binary sensor description."""

    value_fn: Callable[[Super73State], bool | None]


BINARY_SENSORS: tuple[Super73BinarySensorEntityDescription, ...] = (
    Super73BinarySensorEntityDescription(
        key="light",
        translation_key="light",
        device_class=BinarySensorDeviceClass.LIGHT,
        value_fn=lambda state: state.light,
    ),
    Super73BinarySensorEntityDescription(
        key="walk_mode",
        translation_key="walk_mode",
        value_fn=lambda state: state.walk,
    ),
    Super73BinarySensorEntityDescription(
        key="charging",
        translation_key="charging",
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
        value_fn=lambda state: state.charging,
    ),
    Super73BinarySensorEntityDescription(
        key="limp_mode",
        translation_key="limp_mode",
        value_fn=lambda state: state.limp,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up SUPER73 binary sensors."""
    coordinator: Super73DataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            *(
                Super73BinarySensor(coordinator, description)
                for description in BINARY_SENSORS
            ),
            Super73InRangeBinarySensor(coordinator),
        ]
    )


class Super73BinarySensor(
    CoordinatorEntity[Super73DataUpdateCoordinator], BinarySensorEntity
):
    """SUPER73 binary sensor."""

    entity_description: Super73BinarySensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: Super73DataUpdateCoordinator,
        description: Super73BinarySensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.address}_{description.key}"
        self._attr_device_info = coordinator.device_info

    @property
    def is_on(self) -> bool | None:
        """Return the binary sensor state."""
        return self.entity_description.value_fn(self.coordinator.data)


class Super73InRangeBinarySensor(BinarySensorEntity):
    """Whether any Bluetooth scanner currently hears the bike.

    Based on advertisements only, so it stays available while the bike
    cannot be connected to.
    """

    _attr_has_entity_name = True
    _attr_translation_key = "in_range"
    _attr_device_class = BinarySensorDeviceClass.PRESENCE
    _attr_should_poll = False

    def __init__(self, coordinator: Super73DataUpdateCoordinator) -> None:
        """Initialize the sensor."""
        self._presence = coordinator.presence
        self._attr_unique_id = f"{coordinator.address}_in_range"
        self._attr_device_info = coordinator.device_info

    async def async_added_to_hass(self) -> None:
        """Subscribe to presence changes."""
        self.async_on_remove(
            self._presence.async_add_listener(self.async_write_ha_state)
        )

    @property
    def is_on(self) -> bool | None:
        """Return True while the bike is heard."""
        return self._presence.in_range

    @property
    def extra_state_attributes(self) -> dict[str, str | int | None]:
        """Return the scanner that heard the bike when it came into range."""
        return {"source": self._presence.source, "rssi": self._presence.rssi}
