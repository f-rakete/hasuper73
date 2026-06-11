"""Config flow for SUPER73 Bluetooth."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ADDRESS, CONF_NAME
from homeassistant.helpers import selector

from .const import DOMAIN, METRICS_SERVICE


class Super73ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for SUPER73."""

    VERSION = 1
    _discovered_address: str | None = None
    _discovered_name: str | None = None

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Handle Bluetooth discovery."""
        if METRICS_SERVICE not in {uuid.lower() for uuid in discovery_info.service_uuids}:
            return self.async_abort(reason="not_supported")

        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()

        self._discovered_address = discovery_info.address
        self._discovered_name = discovery_info.name or "SUPER73"
        self.context["title_placeholders"] = {
            "name": self._discovered_name,
            "address": discovery_info.address,
        }
        return self.async_show_form(
            step_id="bluetooth_confirm",
            description_placeholders={
                "name": discovery_info.name or "SUPER73",
                "address": discovery_info.address,
            },
        )

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm Bluetooth discovery."""
        if user_input is None:
            return self.async_show_form(step_id="bluetooth_confirm")

        address = self._discovered_address
        name = self._discovered_name or "SUPER73"
        if address is None:
            return self.async_abort(reason="not_supported")

        return self.async_create_entry(
            title=name,
            data={CONF_ADDRESS: address, CONF_NAME: name},
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle manual setup."""
        errors: dict[str, str] = {}
        if user_input is not None:
            address = user_input[CONF_ADDRESS].strip()
            await self.async_set_unique_id(address)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=user_input[CONF_NAME],
                data={CONF_ADDRESS: address, CONF_NAME: user_input[CONF_NAME]},
            )

        schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default="SUPER73"): selector.TextSelector(),
                vol.Required(CONF_ADDRESS): selector.TextSelector(),
            }
        )
        return self.async_show_form(
            step_id="user", data_schema=schema, errors=errors
        )
