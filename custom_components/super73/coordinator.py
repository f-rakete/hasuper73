"""Data coordinator for SUPER73 Bluetooth."""

from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import Super73Client
from .const import DOMAIN
from .models import Super73State

_LOGGER = logging.getLogger(__name__)


class Super73DataUpdateCoordinator(DataUpdateCoordinator[Super73State]):
    """Coordinate SUPER73 state."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        self.config_entry = entry
        self.address: str = entry.data[CONF_ADDRESS]
        self.name: str = entry.data.get(CONF_NAME, "SUPER73")
        self.client = Super73Client(hass, self.address, self.name)
        self.client.register_callback(self._handle_state_update)

        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=10),
            always_update=False,
        )

    @property
    def device_info(self) -> DeviceInfo:
        """Return Home Assistant device info."""
        info = self.client.device_info
        return DeviceInfo(
            identifiers={(DOMAIN, self.address)},
            name=info.name or self.name,
            manufacturer=info.manufacturer or "SUPER73",
            model="Comodule Diamond Display",
            sw_version=info.software_version,
            hw_version=info.hardware_version,
        )

    async def _async_update_data(self) -> Super73State:
        """Fetch data from the bike."""
        try:
            return await self.client.async_update()
        except Exception as err:
            if self.data is not None:
                _LOGGER.debug("Keeping last known SUPER73 state: %s", err)
                return self.data
            raise UpdateFailed(f"Unable to update SUPER73 state: {err}") from err

    async def async_shutdown(self) -> None:
        """Shut down the BLE client."""
        await self.client.async_disconnect()

    @callback
    def _handle_state_update(self, state: Super73State) -> None:
        """Push notification updates to entities."""
        self.async_set_updated_data(state)
