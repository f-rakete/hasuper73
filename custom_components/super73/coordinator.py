"""Data coordinator for SUPER73 Bluetooth."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import Super73Client, describe_error
from .const import DOMAIN, UPDATE_INTERVAL
from .models import Super73State
from .presence import Super73PresenceTracker

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
        self.presence = Super73PresenceTracker(hass, self.address)

        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
            # Each update returns a new state object, so unchanged polls
            # don't write entity states.
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
        """Fetch data from the bike, keeping the last state while it's unreachable."""
        if self.presence.in_range is False:
            return self._keep_last_state("not in range")
        try:
            return await self.client.async_update()
        except Exception as err:  # noqa: BLE001 - BLE stacks fail in many backend-specific ways.
            return self._keep_last_state(describe_error(err))

    def _keep_last_state(self, reason: str) -> Super73State:
        """Return the last known state, or fail if there never was one.

        The bike is off, away, or busy with another central (the official app,
        a Puck.js button) most of the time, so this is normal and only logged
        at debug level. The next poll tries again.
        """
        if self.data is not None:
            _LOGGER.debug("SUPER73 not updated, keeping last known state: %s", reason)
            return self.data
        raise UpdateFailed(f"Unable to update SUPER73 state: {reason}")

    async def async_shutdown(self) -> None:
        """Stop polling and release the bike."""
        await super().async_shutdown()
        await self.client.async_disconnect()
