"""SUPER73 Bluetooth integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import Super73DataUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up SUPER73 from a config entry."""
    coordinator = Super73DataUpdateCoordinator(hass, entry)
    coordinator.presence.async_start()
    entry.async_on_unload(coordinator.presence.async_stop)

    # The bike is usually switched off or away, so setup must not depend on a
    # connection. Entities stay unavailable until the first successful update.
    await coordinator.async_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    coordinator: Super73DataUpdateCoordinator | None = hass.data[DOMAIN].pop(
        entry.entry_id, None
    )
    if coordinator is not None:
        await coordinator.async_shutdown()

    if not hass.data[DOMAIN]:
        hass.data.pop(DOMAIN)

    return unload_ok
