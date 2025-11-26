import logging
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN
from .api import CannotConnect

_LOGGER = logging.getLogger(__name__)


SENSORS = [
    ("t.0", "Air Temperature", SensorDeviceClass.TEMPERATURE, "°C"),
    ("t.1", "Floor Temperature", SensorDeviceClass.TEMPERATURE, "°C"),
    ("t.5", "Heater Power", None, None),
    ("m.1", "Mode", None, None),
    ("o.0", "WiFi RSSI", SensorDeviceClass.SIGNAL_STRENGTH, "dBm"),
    ("o.1", "WiFi Quality", SensorDeviceClass.SIGNAL_STRENGTH, None),
    ("f.10", "Relay State", None, None),
]


async def async_setup_entry(hass, entry, async_add_entities):
    """Создание сенсоров после загрузки интеграции."""
    api = hass.data[DOMAIN][entry.entry_id]["api"]
    name = f"Terneo {entry.data['host']}"

    entities = []

    for key, title, dev_class, unit in SENSORS:
        entities.append(
            TerneoTelemetrySensor(
                api,
                f"{name} {title}",
                key,
                dev_class,
                unit,
                entry.data["host"]
            )
        )

    # Добавляем сенсор уставки температуры из параметров (par.31)
    entities.append(
        TerneoParameterSensor(
            api,
            f"{name} Set Temperature",
            31,  # параметр уставки
            entry.data["host"]
        )
    )

    async_add_entities(entities)


class TerneoTelemetrySensor(SensorEntity):
    """Сенсор для данных телеметрии cmd=4"""

    def __init__(self, api, name, key, device_class, unit, host):
        self.api = api
        self._attr_name = name
        self._key = key
        self._attr_device_class = device_class
        self._attr_native_unit_of_measurement = unit
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._available = False
        self._state = None
        self._host = host

    @property
    def available(self):
        return self._available

    @property
    def state(self):
        return self._state

    @property
    def device_info(self):
        return DeviceInfo(
            identifiers={(DOMAIN, self._host)},
            name=f"Terneo {self._host}",
            manufacturer="Terneo",
        )

    async def async_update(self):
        try:
            telemetry = await self.api.get_telemetry()

            raw = telemetry.get(self._key)

            # Температуры — нужно переводить в °C
            if self._key.startswith("t."):
                try:
                    self._state = round(int(raw) / 10, 1)
                except:
                    self._state = None

            else:
                self._state = raw

            self._available = True

        except CannotConnect:
            self._available = False
        except Exception as e:
            _LOGGER.error("Unexpected telemetry error: %s", e)
            self._available = False


class TerneoParameterSensor(SensorEntity):
    """Сенсор параметров cmd=1 — например, уставка температуры"""

    def __init__(self, api, name, param_index, host):
        self.api = api
        self._attr_name = name
        self._param_index = param_index
        self._state = None
        self._available = False
        self._host = host
        self._attr_device_class = SensorDeviceClass.TEMPERATURE
        self._attr_native_unit_of_measurement = "°C"

    @property
    def available(self):
        return self._available

    @property
    def device_info(self):
        return DeviceInfo(
            identifiers={(DOMAIN, self._host)},
            name=f"Terneo {self._host}",
            manufacturer="Terneo",
        )

    async def async_update(self):
        try:
            params = await self.api.get_parameters()
            par_list = params.get("par", [])

            for p_index, p_type, p_value in par_list:
                if p_index == self._param_index:
                    try:
                        self._state = int(p_value)
                    except:
                        self._state = None

            self._available = True

        except CannotConnect:
            self._available = False
        except Exception as e:
            _LOGGER.error("Error reading parameter %s: %s", self._param_index, e)
            self._available = False
