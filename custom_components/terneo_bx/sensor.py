
from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from .const import DOMAIN, API_TIMEOUT
import async_timeout
import json

async def _api_call(session, host, payload):
    async with async_timeout.timeout(API_TIMEOUT):
        r = await session.post(f"http://{host}/api.cgi", json=payload)
        return await r.json()

async def async_setup_entry(hass, entry, async_add_entities):
    data = hass.data[DOMAIN][entry.entry_id]
    host = data["host"]
    session = async_get_clientsession(hass)

    async_add_entities([
        TerneoPowerSensor(host, session),
        TerneoTelemetrySensor(host, session)
    ], True)

class TerneoPowerSensor(SensorEntity):
    _attr_name="Terneo Power"
    _attr_native_unit_of_measurement="W"

    def __init__(self, host, session):
        self._host=host
        self._session=session
        self._power=0

    async def async_update(self):
        raw = await _api_call(self._session, self._host, {"cmd":1,"par":[]})
        tele = await _api_call(self._session, self._host, {"cmd":4})
        par = raw.get("par", [])
        relay = int(tele.get("f.0",[0])[0])

        enc = 0
        for p in par:
            if p[0]==17:
                enc=int(p[2])

        if enc <=1500:
            power=enc*10
        else:
            power=(enc-1500)*20

        self._power = power if relay==1 else 0

    @property
    def native_value(self):
        return self._power

class TerneoTelemetrySensor(SensorEntity):
    _attr_name="Terneo Relay"
    _attr_native_unit_of_measurement=None

    def __init__(self, host, session):
        self._host=host
        self._session=session
        self._state=0

    async def async_update(self):
        tele = await _api_call(self._session, self._host, {"cmd":4})
        self._state=int(tele.get("f.0",[0])[0])

    @property
    def native_value(self):
        return self._state
