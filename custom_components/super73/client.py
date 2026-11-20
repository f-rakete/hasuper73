"""BLE client for SUPER73/Comodule display metrics.

The bike accepts one Bluetooth connection at a time and stops advertising while
a central is connected. So every update connects, reads all registers and
disconnects again, and the bike is free for other centrals (the official app,
a Puck.js button) between updates.
"""

from __future__ import annotations

import asyncio
import copy
import hashlib
import logging
import time

from bleak_retry_connector import BleakClientWithServiceCache, establish_connection

from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant

from .const import (
    AUTH_CHALLENGE_CHARACTERISTIC,
    AUTH_KEY,
    AUTH_RESPONSE_CHARACTERISTIC,
    AUTH_SERVICE,
    AUTH_STATE_CHARACTERISTIC,
    CONF_ADDRESS,
    CONNECT_ATTEMPTS,
    CONNECT_TIMEOUT_SECONDS,
    DEVICE_INFO_FIRMWARE_CHARACTERISTIC,
    DEVICE_INFO_HARDWARE_CHARACTERISTIC,
    DEVICE_INFO_MANUFACTURER_CHARACTERISTIC,
    DEVICE_INFO_SERVICE,
    DEVICE_INFO_SOFTWARE_CHARACTERISTIC,
    DISCONNECT_TIMEOUT_SECONDS,
    GENERIC_ACCESS_NAME_CHARACTERISTIC,
    GENERIC_ACCESS_SERVICE,
    INFO_REGISTER_IDS,
    INFO_TIMEOUT_SECONDS,
    METRICS_CHARACTERISTIC_REGISTER,
    METRICS_CHARACTERISTIC_REGISTER_ID,
    METRICS_SERVICE,
    OPTIONAL_REGISTER_IDS,
    PAIR_TIMEOUT_SECONDS,
    REGISTER_IDS,
    SESSION_TIMEOUT_SECONDS,
    VERSION_REGISTER_IDS,
)
from .models import Super73DeviceInfo, Super73State
from .protocol import parse_frame, parse_info

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
        # Identity and versions are read once, on the first connection after
        # Home Assistant starts. Reading them has upset the bike's Bluetooth
        # for minutes afterwards, so they are never re-read or retried.
        self._info_pending = True
        self._auth_failed = False
        # Optional registers the bike didn't answer since it came into range.
        self._unserved: set[bytes] = set()
        self._client: BleakClientWithServiceCache | None = None
        self._operation_lock = asyncio.Lock()

    def recheck_optional_registers(self) -> None:
        """Ask again for optional registers the bike didn't answer last time."""
        self._unserved.clear()

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
                if self._info_pending:
                    await self._read_info_session(client)
            finally:
                await self._disconnect(client)
                _LOGGER.debug(
                    "SUPER73 link released after %.1f s",
                    time.monotonic() - connected,
                )
            state.info = copy.deepcopy(self.device_info)
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

        state = Super73State()
        for register_id in REGISTER_IDS:
            frame = await self._read_register(client, register_id)
            self._store_frame(state, register_id, frame)
        for register_id in OPTIONAL_REGISTER_IDS:
            if register_id in self._unserved:
                continue
            frame = await self._read_optional_register(client, register_id)
            if frame is None:
                # Every unanswered read keeps the bike busy for nothing, so
                # don't ask again until the bike next comes into range.
                self._unserved.add(register_id)
            else:
                self._store_frame(state, register_id, frame)
        return state

    @staticmethod
    def _store_frame(state: Super73State, register_id: bytes, frame: bytes) -> None:
        """Decode a frame into state and keep its raw bytes."""
        _LOGGER.debug("SUPER73 frame: %s", frame.hex(" "))
        state.raw_frames[register_id.hex()] = frame.hex(" ")
        parse_frame(frame, state)

    async def _read_info_session(self, client: BleakClientWithServiceCache) -> None:
        """Read static information once, bounded and never failing the update.

        If it doesn't finish, the values read so far are kept and the rest
        stays unknown until Home Assistant restarts.
        """
        self._info_pending = False
        started = time.monotonic()
        frames: dict[bytes, bytes] = {}
        try:
            async with asyncio.timeout(INFO_TIMEOUT_SECONDS):
                await self._read_device_info(client)
                await self._read_info_registers(client, frames)
        except Exception as err:  # noqa: BLE001 - BLE stacks fail in many backend-specific ways.
            _LOGGER.debug(
                "SUPER73 device information incomplete after %.1f s, not retrying: %s",
                time.monotonic() - started,
                describe_error(err),
            )
        else:
            _LOGGER.debug(
                "SUPER73 device information read in %.1f s",
                time.monotonic() - started,
            )
        parse_info(frames, self.device_info)

    async def _read_info_registers(
        self, client: BleakClientWithServiceCache, frames: dict[bytes, bytes]
    ) -> None:
        """Read identity and version registers into frames, authenticating only if needed.

        Each read is logged before it starts, so a hang shows which register
        caused it.
        """
        for register_id in INFO_REGISTER_IDS:
            _LOGGER.debug("SUPER73 reading register %s", register_id.hex())
            frame = await self._read_optional_register(client, register_id)
            if frame is not None:
                frames[register_id] = frame

        authenticated = False
        for register_id in VERSION_REGISTER_IDS:
            _LOGGER.debug("SUPER73 reading register %s", register_id.hex())
            frame = await self._read_optional_register(client, register_id)
            if frame is None and not authenticated and not self._auth_failed:
                authenticated = await self._authenticate(client)
                if not authenticated:
                    self._auth_failed = True
                    continue
                frame = await self._read_optional_register(client, register_id)
            if frame is not None:
                frames[register_id] = frame

    async def _authenticate(self, client: BleakClientWithServiceCache) -> bool:
        """Answer the security service's challenge the way the official app does.

        Returns False if the bike has no security service or rejects the
        answer. A rejected answer makes the bike disconnect.
        """
        if client.services.get_service(AUTH_SERVICE) is None:
            _LOGGER.debug("SUPER73 has no security service; versions stay unknown")
            return False
        try:
            challenge = bytes(await client.read_gatt_char(AUTH_CHALLENGE_CHARACTERISTIC))
            await client.write_gatt_char(
                AUTH_RESPONSE_CHARACTERISTIC,
                hashlib.sha1(challenge + AUTH_KEY).digest(),
                response=True,
            )
            result = bytes(await client.read_gatt_char(AUTH_STATE_CHARACTERISTIC))
        except Exception as err:  # noqa: BLE001 - BLE stacks fail in many backend-specific ways.
            _LOGGER.debug(
                "SUPER73 authentication failed, not retrying: %s", describe_error(err)
            )
            return False
        if not result or result[0] == 0:
            _LOGGER.debug("SUPER73 rejected authentication, not retrying")
            return False
        _LOGGER.debug("SUPER73 authenticated")
        return True

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
        """Read static GATT device metadata."""
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
        info.firmware_version = await self._read_text(
            client, DEVICE_INFO_SERVICE, DEVICE_INFO_FIRMWARE_CHARACTERISTIC
        ) or info.firmware_version
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
        _LOGGER.debug("SUPER73 reading characteristic %s", characteristic_uuid[4:8])
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

    async def _read_optional_register(
        self, client: BleakClientWithServiceCache, register_id: bytes
    ) -> bytes | None:
        """Read a register some bikes may not serve.

        Returns None unless the bike answers with a frame for this register,
        so an unanswered register is unknown rather than zero. A bike that
        doesn't serve a register returns the previously selected frame. Only a
        lost connection raises.
        """
        try:
            # No pair-and-retry: the link is already encrypted by now, so a
            # refusal here is about the register, and pairing can take 10 s.
            frame = await self._read_register_once(client, register_id)
        except Exception as err:  # noqa: BLE001 - BLE stacks fail in many backend-specific ways.
            if not client.is_connected:
                raise
            _LOGGER.debug(
                "SUPER73 register %s not readable: %s",
                register_id.hex(),
                describe_error(err),
            )
            return None
        if len(frame) != 10 or frame[:2] != register_id:
            _LOGGER.debug(
                "SUPER73 register %s not served (got %s)",
                register_id.hex(),
                frame.hex(" "),
            )
            return None
        return frame

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
