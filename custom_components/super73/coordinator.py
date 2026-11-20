"""Data coordinator for SUPER73 Bluetooth."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
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
        self._was_in_range: bool | None = None
        self._registry_info: dict[str, str] = {}
        entry.async_on_unload(
            self.presence.async_add_listener(self._handle_presence_change)
        )

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
            serial_number=self.presence.module_id,
        )

    @callback
    def _handle_presence_change(self) -> None:
        """Ask again for unanswered optional registers each time the bike comes into range."""
        in_range = self.presence.in_range
        if in_range and self._was_in_range is False:
            self.client.recheck_optional_registers()
        self._was_in_range = in_range

    async def _async_update_data(self) -> Super73State:
        """Fetch data from the bike, keeping the last state while it's unreachable."""
        if self.presence.in_range is False:
            return self._keep_last_state("not in range")
        try:
            state = await self.client.async_update()
        except Exception as err:  # noqa: BLE001 - BLE stacks fail in many backend-specific ways.
            return self._keep_last_state(describe_error(err))
        self._async_update_device_registry()
        return state

    @callback
    def _async_update_device_registry(self) -> None:
        """Show versions read after setup on the device page.

        Entities register the device with what was known at setup, which is
        nothing when the bike was off or away then.
        """
        info = self.client.device_info
        wanted = {
            key: value
            for key, value in (
                ("sw_version", info.software_version),
                ("hw_version", info.hardware_version),
                ("serial_number", self.presence.module_id),
            )
            if value is not None
        }
        if wanted == self._registry_info:
            return
        registry = dr.async_get(self.hass)
        device = registry.async_get_device(identifiers={(DOMAIN, self.address)})
        if device is None:
            return
        registry.async_update_device(device.id, **wanted)
        self._registry_info = wanted

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
