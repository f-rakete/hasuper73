"""BLE client for SUPER73/Comodule display metrics."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
import logging

from bleak import BleakClient
from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.backends.device import BLEDevice
from bleak_retry_connector import establish_connection

from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant, callback

from .const import (
    CONF_ADDRESS,
    DEVICE_INFO_HARDWARE_CHARACTERISTIC,
    DEVICE_INFO_MANUFACTURER_CHARACTERISTIC,
    DEVICE_INFO_SERVICE,
    DEVICE_INFO_SOFTWARE_CHARACTERISTIC,
    GENERIC_ACCESS_NAME_CHARACTERISTIC,
    GENERIC_ACCESS_SERVICE,
    METRICS_CHARACTERISTIC_REGISTER,
    METRICS_CHARACTERISTIC_REGISTER_ID,
    METRICS_CHARACTERISTIC_REGISTER_NOTIFIER,
    METRICS_SERVICE,
    REGISTER_IDS,
)
from .models import Super73DeviceInfo, Super73State
from .protocol import parse_frame

_LOGGER = logging.getLogger(__name__)

StateCallback = Callable[[Super73State], None]


class Super73Client:
    """Async BLE client for the Comodule Diamond Display protocol."""

    def __init__(self, hass: HomeAssistant, address: str, name: str | None) -> None:
        """Initialize the client."""
        self._hass = hass
        self.address = address
        self.name = name or "SUPER73"
        self.state = Super73State()
        self.device_info = Super73DeviceInfo(name=self.name)
        self._client: BleakClient | None = None
        self._callbacks: list[StateCallback] = []
        self._operation_lock = asyncio.Lock()

    def register_callback(self, callback_fn: StateCallback) -> None:
        """Register a callback for parsed state changes."""
        self._callbacks.append(callback_fn)

    async def async_update(self) -> Super73State:
        """Connect if needed and refresh all known registers."""
        async with self._operation_lock:
            await self._ensure_connected()
            await self._read_startup_info()
            for register_id in REGISTER_IDS:
                await self._read_register(register_id)
        return self.state

    async def async_disconnect(self) -> None:
        """Disconnect from the bike."""
        client = self._client
        self._client = None
        if client is not None and client.is_connected:
            await client.disconnect()

    async def _ensure_connected(self) -> None:
        """Ensure the BLE connection is available."""
        if self._client is not None and self._client.is_connected:
            return

        device = bluetooth.async_ble_device_from_address(
            self._hass, self.address, connectable=True
        )
        if device is None:
            raise ConnectionError(f"No connectable Bluetooth device found for {self.address}")

        self._client = await establish_connection(
            BleakClient,
            device,
            self.name,
            self._disconnected,
        )

        services = self._client.services
        if METRICS_SERVICE not in {service.uuid for service in services}:
            await self.async_disconnect()
            raise ConnectionError("Device does not expose the SUPER73 metrics service")

        await self._client.start_notify(
            METRICS_CHARACTERISTIC_REGISTER_NOTIFIER,
            self._notification_handler,
        )

    async def _read_startup_info(self) -> None:
        """Read optional GATT device metadata."""
        client = self._require_client()
        self.device_info.name = await self._read_text(
            client, GENERIC_ACCESS_SERVICE, GENERIC_ACCESS_NAME_CHARACTERISTIC
        ) or self.device_info.name
        self.device_info.manufacturer = await self._read_text(
            client, DEVICE_INFO_SERVICE, DEVICE_INFO_MANUFACTURER_CHARACTERISTIC
        ) or self.device_info.manufacturer
        self.device_info.software_version = await self._read_text(
            client, DEVICE_INFO_SERVICE, DEVICE_INFO_SOFTWARE_CHARACTERISTIC
        ) or self.device_info.software_version
        self.device_info.hardware_version = await self._read_text(
            client, DEVICE_INFO_SERVICE, DEVICE_INFO_HARDWARE_CHARACTERISTIC
        ) or self.device_info.hardware_version

    async def _read_text(
        self, client: BleakClient, service_uuid: str, characteristic_uuid: str
    ) -> str | None:
        """Read a text characteristic if present."""
        try:
            service = client.services.get_service(service_uuid)
            if service is None or service.get_characteristic(characteristic_uuid) is None:
                return None
            raw = await client.read_gatt_char(characteristic_uuid)
        except Exception as err:  # noqa: BLE001 - BLE stacks fail in many backend-specific ways.
            _LOGGER.debug("Unable to read %s: %s", characteristic_uuid, err)
            return None
        return bytes(raw).decode("ascii", errors="ignore").strip("\x00") or None

    async def _read_register(self, register_id: bytes) -> None:
        """Select and read a metrics register."""
        client = self._require_client()
        await client.write_gatt_char(
            METRICS_CHARACTERISTIC_REGISTER_ID, register_id, response=True
        )
        raw = bytes(await client.read_gatt_char(METRICS_CHARACTERISTIC_REGISTER))
        self._process_frame(raw)

    def _process_frame(self, raw: bytes) -> None:
        """Process one 10-byte metrics frame."""
        _LOGGER.debug("SUPER73 frame: %s", raw.hex(" "))
        if parse_frame(raw, self.state):
            self._notify_state_changed()

    def _notification_handler(
        self, _characteristic: BleakGATTCharacteristic, data: bytearray
    ) -> None:
        """Handle register notifier updates."""
        self._process_frame(bytes(data))

    @callback
    def _notify_state_changed(self) -> None:
        """Notify listeners that parsed state changed."""
        for callback_fn in self._callbacks:
            callback_fn(self.state)

    def _disconnected(self, _device: BLEDevice) -> None:
        """Handle BLE disconnection."""
        self._client = None

    def _require_client(self) -> BleakClient:
        """Return the active BLE client."""
        if self._client is None or not self._client.is_connected:
            raise ConnectionError("SUPER73 is not connected")
        return self._client


def client_from_entry(hass: HomeAssistant, data: dict[str, str]) -> Super73Client:
    """Create a client from config entry data."""
    return Super73Client(hass, data[CONF_ADDRESS], data.get("name"))
