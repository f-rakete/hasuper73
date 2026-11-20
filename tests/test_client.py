"""Scratch: drive Super73Client against a fake bike (needs homeassistant installed; run with python tests/test_client.py)."""

import asyncio
import hashlib
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from custom_components.super73 import client as client_mod  # noqa: E402
from custom_components.super73 import const  # noqa: E402

LIVE = {
    "0300": "03 00 04 00 01 07 00 00 00 00",
    "0202": "02 02 00 24 00 00 70 11 01 00",
    "0203": "02 03 00 0c 00 00 00 00 2c 01",
    "0401": "04 01 aa d2 00 00 00 00 00 00",
    "0201": "02 01 c4 09 00 00 00 00 00 00",
    "0402": "04 02 55 00 00 00 00 00 00 00",
    "0200": "02 00 00 00 00 00 00 00 25 00",
    "0210": "02 10 52 58 20 20 20 00 31 32",
    "0211": "02 11 33 34 35 36 37 38 39 30",
    "0212": "02 12 45 55 00 00 00 00 00 00",
}
VERSIONS = {
    "fcfc": "fc fc 03 11 37 00 00 06 e7 00",
    "fafa": "fa fa 00 00 01 9a 00 00 00 00",
}
CHALLENGE = bytes(range(20))


class FakeService:
    def get_characteristic(self, uuid):
        return object() if uuid == const.DEVICE_INFO_FIRMWARE_CHARACTERISTIC else None


class FakeServices:
    def __init__(self, uuids):
        self._uuids = uuids

    def get_service(self, uuid):
        return FakeService() if uuid in self._uuids else None


class FakeBike:
    def __init__(self, *, versions_need_auth=True, accept_auth=True, missing=()):
        self.versions_need_auth = versions_need_auth
        self.accept_auth = accept_auth
        self.missing = set(missing)
        self.services = FakeServices(
            {const.METRICS_SERVICE, const.AUTH_SERVICE, const.DEVICE_INFO_SERVICE}
        )
        self.is_connected = True
        self.selected = None
        self.last_frame = bytes(10)
        self.authed = False
        self.auth_attempts = 0
        self.reads = []

    def _check(self):
        if not self.is_connected:
            raise ConnectionError("disconnected")

    async def pair(self):
        self._check()

    async def disconnect(self):
        self.is_connected = False

    async def write_gatt_char(self, char, data, response=True):
        self._check()
        if char == const.METRICS_CHARACTERISTIC_REGISTER_ID:
            self.selected = bytes(data).hex()
        elif char == const.AUTH_RESPONSE_CHARACTERISTIC:
            self.auth_attempts += 1
            expected = hashlib.sha1(CHALLENGE + bytes([0xFF] * 20)).digest()
            if bytes(data) == expected and self.accept_auth:
                self.authed = True
            else:
                # The display disconnects on a wrong answer (reason 0x13).
                self.is_connected = False
                raise ConnectionError("disconnected by peer")

    async def read_gatt_char(self, char):
        self._check()
        if char == const.METRICS_CHARACTERISTIC_REGISTER:
            self.reads.append(self.selected)
            sel = self.selected
            if sel in LIVE and sel not in self.missing:
                self.last_frame = bytes.fromhex(LIVE[sel])
            elif sel in VERSIONS and (self.authed or not self.versions_need_auth):
                self.last_frame = bytes.fromhex(VERSIONS[sel])
            # Unserved register: the previous frame comes back unchanged.
            return bytearray(self.last_frame)
        if char == const.METRICS_CHARACTERISTIC_REGISTER_NOTIFIER:
            return bytearray(self.last_frame)
        if char == const.AUTH_CHALLENGE_CHARACTERISTIC:
            return bytearray(CHALLENGE)
        if char == const.AUTH_STATE_CHARACTERISTIC:
            return bytearray([1 if self.authed else 0])
        if char == const.DEVICE_INFO_FIRMWARE_CHARACTERISTIC:
            return bytearray(b"221122")
        raise ValueError(f"unexpected read {char}")


def make_client(bike):
    async def fake_connect(*_args, **_kwargs):
        bike.is_connected = True
        bike.selected = None
        bike.authed = False
        return bike

    client_mod.bluetooth.async_ble_device_from_address = lambda *a, **k: object()
    client_mod.establish_connection = fake_connect
    return client_mod.Super73Client(hass=None, address="F5:14:76:B9:41:BA", name="SUPER73")


async def main():
    # A: everything served, versions need app authentication.
    bike = FakeBike()
    c = make_client(bike)
    s = await c.async_update()
    assert s.battery_level == 85.0 and s.total_km == 7000.0 and s.warning_codes == (14, 17)
    assert s.info.controller_version == 410 and s.info.stm_version == 201015, s.info
    assert s.info.bike_model == "RX" and s.info.region == "EU"
    assert s.info.firmware_version == "221122"
    assert bike.auth_attempts == 1 and c._info_pending is False
    assert set(s.raw_frames) == {"0300", "0202", "0203", "0401", "0201", "0402", "0200"}
    assert set(s.info.raw_frames) == {"0210", "0211", "0212", "fcfc", "fafa"}
    # Second update: no info reads, no auth, info snapshot carried over.
    bike.reads.clear()
    s2 = await c.async_update()
    assert bike.reads == ["0300", "0202", "0203", "0401", "0201", "0402", "0200"], bike.reads
    assert bike.auth_attempts == 1 and s2.info.controller_version == 410
    assert s2 == s, "unchanged bike gives an equal state, so entities aren't rewritten"
    # Coming into range again doesn't re-read info: it's read once per HA start.
    c.recheck_optional_registers()
    bike.reads.clear()
    await c.async_update()
    assert bike.auth_attempts == 1 and "fcfc" not in bike.reads, bike.reads

    # B: versions served without auth -> no auth attempt at all.
    bike = FakeBike(versions_need_auth=False)
    c = make_client(bike)
    s = await c.async_update()
    assert bike.auth_attempts == 0 and s.info.controller_version == 410

    # C: auth rejected -> bike disconnects. Live values survive, identity read
    # before the failure is kept, and nothing is retried.
    bike = FakeBike(accept_auth=False)
    c = make_client(bike)
    s = await c.async_update()
    assert s.battery_level == 85.0 and s.info.controller_version is None
    assert s.info.bike_model == "RX", "identity read before the failure is kept"
    assert c._auth_failed and not c._info_pending
    c.recheck_optional_registers()
    bike.reads.clear()
    await c.async_update()
    assert "fcfc" not in bike.reads and bike.auth_attempts == 1, bike.reads

    # D: a bike without SoC / warning registers: estimate + unknown, no failure.
    bike = FakeBike(missing={"0402", "0200", "0210", "0211", "0212"}, versions_need_auth=False)
    c = make_client(bike)
    s = await c.async_update()
    assert s.state_of_charge is None and s.battery_level == 100.0  # 300 km vs 60 km base
    assert s.warning_codes is None and s.warning is None
    assert s.info.bike_model is None and s.info.controller_version == 410
    assert "0402" not in s.raw_frames
    # Unanswered optional registers aren't asked again until the bike comes
    # back into range.
    bike.reads.clear()
    await c.async_update()
    assert bike.reads == ["0300", "0202", "0203", "0401", "0201"], bike.reads
    c.recheck_optional_registers()
    bike.reads.clear()
    await c.async_update()
    assert "0402" in bike.reads and "0200" in bike.reads, bike.reads

    # E: a core register failing still fails the update.
    bike = FakeBike()
    c = make_client(bike)

    async def broken(char):
        raise RuntimeError("GATT error")

    bike.read_gatt_char = broken
    try:
        await c.async_update()
    except RuntimeError:
        pass
    else:
        raise AssertionError("core read failure must fail the update")

    print("client checks passed")


asyncio.run(main())
