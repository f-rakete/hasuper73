"""Advertisement-based presence tracking for SUPER73 Bluetooth."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
import logging
import time

from homeassistant.components import bluetooth
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_interval

from .const import PRESENCE_CHECK_INTERVAL, PRESENCE_TIMEOUT_SECONDS

_LOGGER = logging.getLogger(__name__)


class Super73PresenceTracker:
    """Track whether any Bluetooth scanner currently hears the bike.

    This only listens to advertisements and never connects, so passive
    scanners (for example Shelly devices) count as well.
    """

    def __init__(self, hass: HomeAssistant, address: str) -> None:
        """Initialize the tracker."""
        self._hass = hass
        self.address = address
        self.in_range: bool | None = None
        self.source: str | None = None
        self.rssi: int | None = None
        self._last_seen: float | None = None
        self._started: float | None = None
        self._listeners: list[Callable[[], None]] = []
        self._unsubs: list[CALLBACK_TYPE] = []

    @callback
    def async_start(self) -> None:
        """Start listening for advertisements."""
        self._started = time.monotonic()
        self._unsubs.append(
            bluetooth.async_register_advertisement_callback(
                self._hass, self._async_handle_advertisement, self.address
            )
        )
        self._unsubs.append(
            async_track_time_interval(
                self._hass, self._async_check_timeout, PRESENCE_CHECK_INTERVAL
            )
        )

    @callback
    def async_stop(self) -> None:
        """Stop listening for advertisements."""
        while self._unsubs:
            self._unsubs.pop()()

    @callback
    def async_add_listener(self, listener: Callable[[], None]) -> CALLBACK_TYPE:
        """Register a listener for presence changes."""
        self._listeners.append(listener)

        @callback
        def _remove() -> None:
            self._listeners.remove(listener)

        return _remove

    @callback
    def _async_handle_advertisement(
        self, service_info: bluetooth.BluetoothServiceInfoBleak
    ) -> None:
        """Handle one advertisement packet from any scanner."""
        self._last_seen = time.monotonic()
        if self.in_range:
            return
        scanner = bluetooth.async_scanner_by_source(self._hass, service_info.source)
        self.source = scanner.name if scanner is not None else service_info.source
        self.rssi = service_info.rssi
        _LOGGER.debug("SUPER73 in range via %s (rssi %s)", self.source, self.rssi)
        self._async_set_in_range(True)

    @callback
    def _async_check_timeout(self, _now: datetime) -> None:
        """Mark the bike out of range once advertisements stop."""
        if self.in_range is False:
            return
        last_heard = self._last_seen if self._last_seen is not None else self._started
        if last_heard is None or time.monotonic() - last_heard < PRESENCE_TIMEOUT_SECONDS:
            return
        _LOGGER.debug("SUPER73 out of range")
        self._async_set_in_range(False)

    @callback
    def _async_set_in_range(self, in_range: bool) -> None:
        """Update presence and notify listeners."""
        self.in_range = in_range
        for listener in list(self._listeners):
            listener()
