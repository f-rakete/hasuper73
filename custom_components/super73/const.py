"""Constants for the SUPER73 Bluetooth integration."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.const import CONF_ADDRESS, CONF_NAME

DOMAIN = "super73"

LOCAL_NAME_MATCHERS = ("SUPER73*", "Super73*", "super73*")

GENERIC_ACCESS_SERVICE = "00001800-0000-1000-8000-00805f9b34fb"
GENERIC_ACCESS_NAME_CHARACTERISTIC = "00002a00-0000-1000-8000-00805f9b34fb"

DEVICE_INFO_SERVICE = "0000180a-0000-1000-8000-00805f9b34fb"
DEVICE_INFO_MANUFACTURER_CHARACTERISTIC = "00002a29-0000-1000-8000-00805f9b34fb"
DEVICE_INFO_HARDWARE_CHARACTERISTIC = "00002a27-0000-1000-8000-00805f9b34fb"
DEVICE_INFO_FIRMWARE_CHARACTERISTIC = "00002a26-0000-1000-8000-00805f9b34fb"
DEVICE_INFO_SOFTWARE_CHARACTERISTIC = "00002a28-0000-1000-8000-00805f9b34fb"

METRICS_SERVICE = "00001554-1212-efde-1523-785feabcd123"
METRICS_CHARACTERISTIC_REGISTER_ID = "00001564-1212-efde-1523-785feabcd123"
METRICS_CHARACTERISTIC_REGISTER = "0000155f-1212-efde-1523-785feabcd123"
METRICS_CHARACTERISTIC_REGISTER_NOTIFIER = "0000155e-1212-efde-1523-785feabcd123"

# Application authentication, as reverse.bike's sdcfw does it before reading
# the version registers: SHA-1 over the 20-byte challenge followed by the key,
# then read the state (non-zero = authenticated). A wrong answer makes the bike
# disconnect, so a failure is not retried.
AUTH_SERVICE = "00002554-1212-efde-1523-785feabcd123"
AUTH_CHALLENGE_CHARACTERISTIC = "00002556-1212-efde-1523-785feabcd123"
AUTH_RESPONSE_CHARACTERISTIC = "00002557-1212-efde-1523-785feabcd123"
AUTH_STATE_CHARACTERISTIC = "00002558-1212-efde-1523-785feabcd123"
AUTH_KEY = bytes([0xFF] * 20)

# Advertised manufacturer data: the first 8 bytes are the Comodule module ID
# (the one the official app shows under Bike passport > Module data).
COMODULE_MANUFACTURER_ID = 0x020F

# A register frame is the 2-byte register ID followed by 8 data bytes. Most
# registers are the controller's CAN frames passed through unchanged, so the
# register ID is the CAN ID and the data bytes are the CAN payload.
MYSTERY_ID = bytes((0x00, 0x00))
WARNING_ID = bytes((0x02, 0x00))
MOTION_ID = bytes((0x02, 0x01))
TOTAL_ID = bytes((0x02, 0x02))
RIDE_ID = bytes((0x02, 0x03))
BIKE_MODEL_ID = bytes((0x02, 0x10))
BIKE_SERIAL_ID = bytes((0x02, 0x11))
REGION_ID = bytes((0x02, 0x12))
SETTINGS_ID = bytes((0x03, 0x00))
POWER_ID = bytes((0x04, 0x01))
STATE_OF_CHARGE_ID = bytes((0x04, 0x02))
MODULE_VERSIONS_ID = bytes((0xFC, 0xFC))
VERSIONS_ID = bytes((0xFA, 0xFA))

# Read on every update; a failure fails the update. MYSTERY_ID is not decoded,
# so it isn't read; every read keeps the bike busy a little longer.
REGISTER_IDS = (
    SETTINGS_ID,
    TOTAL_ID,
    RIDE_ID,
    POWER_ID,
    MOTION_ID,
)

# Also read on every update, but not every bike may serve them, so a failure
# only leaves their values unknown.
OPTIONAL_REGISTER_IDS = (
    STATE_OF_CHARGE_ID,
    WARNING_ID,
)

# Identity registers that don't change while the bike runs. Read once, on the
# first connection after Home Assistant starts.
INFO_REGISTER_IDS = (
    BIKE_MODEL_ID,
    BIKE_SERIAL_ID,
    REGION_ID,
)

# Version registers, read on the same schedule. sdcfw authenticates before
# reading them; this integration tries without first and authenticates only if
# the bike doesn't answer.
VERSION_REGISTER_IDS = (
    MODULE_VERSIONS_ID,
    VERSIONS_ID,
)

DEFAULT_WHEEL_DIAMETER_M = 0.57
DEFAULT_BASE_MAX_RANGE_KM = 60.0
DEFAULT_CHARGE_CURRENT_THRESHOLD_A = 2.0

# The bike takes one connection at a time, so each update connects, reads and
# disconnects. A Puck.js button holds the bike about 3 s per press and waits
# about 4 s for it to advertise, so updates must release the link quickly.
UPDATE_INTERVAL = timedelta(seconds=10)
CONNECT_TIMEOUT_SECONDS = 15
CONNECT_ATTEMPTS = 2
PAIR_TIMEOUT_SECONDS = 10
# Upper bound for pairing plus all reads, which should take about a second.
SESSION_TIMEOUT_SECONDS = 15
# Separate bound for the one-time device information, identity and version
# reads, so they can't fail an update that already has its values. They took
# 2.5 s on an S2 when they worked; a failure is not retried.
INFO_TIMEOUT_SECONDS = 8
DISCONNECT_TIMEOUT_SECONDS = 10

# The bike switches itself off after 5 minutes idle, so a few minutes without
# advertisements means it is off or gone.
PRESENCE_TIMEOUT_SECONDS = 180
PRESENCE_CHECK_INTERVAL = timedelta(seconds=30)

CONF_BASE_MAX_RANGE_KM = "base_max_range_km"
CONF_REAL_MAX_RANGE_KM = "real_max_range_km"
CONF_WHEEL_DIAMETER_M = "wheel_diameter_m"
CONF_CELL_S_COUNT = "cell_s_count"
CONF_CHARGE_CURRENT_THRESHOLD_A = "charge_current_threshold_a"
