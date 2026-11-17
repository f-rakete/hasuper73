"""BLE client for SUPER73/Comodule display metrics.

The bike accepts one Bluetooth connection at a time and stops advertising while
a central is connected. So every update connects, reads all registers and
disconnects again, and the bike is free for other centrals (the official app,
a Puck.js button) between updates.
"""

from __future__ import annotations

import asyncio
import logging
import time

from bleak_retry_connector import BleakClientWithServiceCache, establish_connection

from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant

from .const import (
    CONF_ADDRESS,
    CONNECT_ATTEMPTS,
    CONNECT_TIMEOUT_SECONDS,
    DEVICE_INFO_HARDWARE_CHARACTERISTIC,
    DEVICE_INFO_MANUFACTURER_CHARACTERISTIC,
    DEVICE_INFO_SERVICE,
    DEVICE_INFO_SOFTWARE_CHARACTERISTIC,
    DISCONNECT_TIMEOUT_SECONDS,
    GENERIC_ACCESS_NAME_CHARACTERISTIC,
    GENERIC_ACCESS_SERVICE,
    METRICS_CHARACTERISTIC_REGISTER,
    METRICS_CHARACTERISTIC_REGISTER_ID,
    METRICS_SERVICE,
    PAIR_TIMEOUT_SECONDS,
    REGISTER_IDS,
    SESSION_TIMEOUT_SECONDS,
)
from .models import Super73DeviceInfo, Super73State
from .protocol import parse_frame

_LOGGER = logging.getLogger(__name__)


class Super73Unavailable(Exception):
    """The bike can't be reached right now: off, away, or busy with another central."""


def describe_error(err: BaseException) -> str:
    """Return an error's message, or its type for message-less ones like timeouts."""
    return str(err) or type(err).__name__


class Super73Client:
    """Async BLE client for the Comodule Diamond Display protocol."""

    def __init__(self, hass: HomeAssistant, address: str, name: str | None) -> None:
        """Initialize the client."""
        self._hass = hass
        self.address = address
        self.name = name or "SUPER73"
        self.state = Super73State()
        self.device_info = Super73DeviceInfo(name=self.name)
        self._device_info_read = False
        self._client: BleakClientWithServiceCache | None = None
        self._operation_lock = asyncio.Lock()

    async def async_update(self) -> Super73State:
        """Connect, read every register into a fresh state, and disconnect.

        Raises Super73Unavailable when the bike can't be connected to. Callers
        should treat that as "try again next poll".
        """
        async with self._operation_lock:
            client = await self._connect()
            connected = time.monotonic()
            try:
                async with asyncio.timeout(SESSION_TIMEOUT_SECONDS):
                    state = await self._read_session(client)
            finally:
                await self._disconnect(client)
                _LOGGER.debug(
                    "SUPER73 link released after %.1f s",
                    time.monotonic() - connected,
                )
            self.state = state
            return state

    async def async_disconnect(self) -> None:
        """Disconnect from the bike if an update is holding the link."""
        if self._client is not None:
            await self._disconnect(self._client)

    async def _connect(self) -> BleakClientWithServiceCache:
        """Open a connection, bounded so a missing bike can't stall the poll."""
        device = bluetooth.async_ble_device_from_address(
            self._hass, self.address, connectable=True
        )
        if device is None:
            raise Super73Unavailable("no connectable Bluetooth scanner hears the bike")

        started = time.monotonic()
        try:
            async with asyncio.timeout(CONNECT_TIMEOUT_SECONDS):
                client = await establish_connection(
                    BleakClientWithServiceCache,
                    device,
                    self.name,
                    max_attempts=CONNECT_ATTEMPTS,
                    ble_device_callback=lambda: bluetooth.async_ble_device_from_address(
                        self._hass, self.address, connectable=True
                    )
                    or device,
                )
        except Exception as err:  # noqa: BLE001 - BLE stacks fail in many backend-specific ways.
            raise Super73Unavailable(
                f"connect failed after {time.monotonic() - started:.1f} s: "
                f"{describe_error(err)}"
            ) from err
        self._client = client
        _LOGGER.debug("SUPER73 connected in %.1f s", time.monotonic() - started)
        return client

    async def _read_session(self, client: BleakClientWithServiceCache) -> Super73State:
        """Read everything needed for one update over an open connection."""
        if client.services.get_service(METRICS_SERVICE) is None:
            raise ConnectionError("Device does not expose the SUPER73 metrics service")

        await self._pair(client)
        if not self._device_info_read:
            await self._read_device_info(client)
            self._device_info_read = True

        state = Super73State()
        for register_id in REGISTER_IDS:
            frame = await self._read_register(client, register_id)
            _LOGGER.debug("SUPER73 frame: %s", frame.hex(" "))
            parse_frame(frame, state)
        return state

    async def _pair(self, client: BleakClientWithServiceCache) -> None:
        """Pair (or re-encrypt with the stored bond) so register reads are allowed.

        The bike rejects register reads on an unencrypted link. Failures are
        not fatal here; the read retries after pairing again.
        """
        started = time.monotonic()
        try:
            async with asyncio.timeout(PAIR_TIMEOUT_SECONDS):
                await client.pair()
        except Exception as err:  # noqa: BLE001 - pairing support depends on backend.
            _LOGGER.debug(
                "Unable to pair with SUPER73: %s", describe_error(err)
            )
            return
        _LOGGER.debug("SUPER73 paired in %.1f s", time.monotonic() - started)

    async def _read_device_info(self, client: BleakClientWithServiceCache) -> None:
        """Read static GATT device metadata (once per Home Assistant run)."""
        info = self.device_info
        info.name = await self._read_text(
            client, GENERIC_ACCESS_SERVICE, GENERIC_ACCESS_NAME_CHARACTERISTIC
        ) or info.name
        info.manufacturer = await self._read_text(
            client, DEVICE_INFO_SERVICE, DEVICE_INFO_MANUFACTURER_CHARACTERISTIC
        ) or info.manufacturer
        info.software_version = await self._read_text(
            client, DEVICE_INFO_SERVICE, DEVICE_INFO_SOFTWARE_CHARACTERISTIC
        ) or info.software_version
        info.hardware_version = await self._read_text(
            client, DEVICE_INFO_SERVICE, DEVICE_INFO_HARDWARE_CHARACTERISTIC
        ) or info.hardware_version

    async def _read_text(
        self,
        client: BleakClientWithServiceCache,
        service_uuid: str,
        characteristic_uuid: str,
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

    async def _read_register(
        self, client: BleakClientWithServiceCache, register_id: bytes
    ) -> bytes:
        """Select and read a metrics register, pairing again if the bike asks."""
        try:
            return await self._read_register_once(client, register_id)
        except Exception as err:
            if "insufficient" not in str(err).lower():
                raise
            _LOGGER.debug("SUPER73 register read requires authentication; pairing")
            await self._pair(client)
            return await self._read_register_once(client, register_id)

    async def _read_register_once(
        self, client: BleakClientWithServiceCache, register_id: bytes
    ) -> bytes:
        """Select and read a metrics register once."""
        await client.write_gatt_char(
            METRICS_CHARACTERISTIC_REGISTER_ID, register_id, response=True
        )
        return bytes(await client.read_gatt_char(METRICS_CHARACTERISTIC_REGISTER))

    async def _disconnect(self, client: BleakClientWithServiceCache) -> None:
        """Disconnect, bounded so a stuck proxy can't block the next poll."""
        if self._client is client:
            self._client = None
        try:
            async with asyncio.timeout(DISCONNECT_TIMEOUT_SECONDS):
                await client.disconnect()
        except Exception as err:  # noqa: BLE001 - BLE stacks fail in many backend-specific ways.
            _LOGGER.debug(
                "Unable to disconnect from SUPER73 cleanly: %s",
                describe_error(err),
            )


def client_from_entry(hass: HomeAssistant, data: dict[str, str]) -> Super73Client:
    """Create a client from config entry data."""
    return Super73Client(hass, data[CONF_ADDRESS], data.get("name"))
