from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN
from .api import TerneoApi, CannotConnect
from .coordinator import TerneoCoordinator

_LOGGER = logging.getLogger(__name__)

# sensor definitions: (key in coordinator.data, name suffix, device_class, unit, state_class)
SENSOR_DEFS = [
    ("temp_air", "Air Temperature", SensorDeviceClass.TEMPERATURE, "°C", SensorStateClass.MEASUREMENT),
    ("temp_floor", "Floor Temperature", SensorDeviceClass.TEMPERATURE, "°C", SensorStateClass.MEASUREMENT),
    ("target_temp", "Target Temperature", SensorDeviceClass.TEMPERATURE, "°C", SensorStateClass.MEASUREMENT),
    ("power_w", "Power", None, "W", SensorStateClass.MEASUREMENT),
    ("wifi_rssi", "WiFi RSSI", SensorDeviceClass.SIGNAL_STRENGTH, "dBm", SensorStateClass.MEASUREMENT),
]


async def async_setup_entry(hass, entry, async_add_entities):
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: TerneoCoordinator = data["coordinator"]
    api: TerneoApi = data["api"]
    host = entry.data["host"]

    entities = []
    for key, title, dev_class, unit, state_class in SENSOR_DEFS:
        entities.append(TerneoCoordinatorSensor(coordinator, api, host, key, title, dev_class, unit, state_class))

    async_add_entities(entities, update_before_add=True)


class TerneoCoordinatorSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator: TerneoCoordinator, api: TerneoApi, host: str, key: str, title: str, dev_class, unit: str | None, state_class):
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.api = api
        self._host = host
        self._key = key
        self._attr_name = f"Terneo {host} {title}"
        self._attr_device_class = dev_class
        self._attr_native_unit_of_measurement = unit
        self._attr_state_class = state_class

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(identifiers={(DOMAIN, self._host)}, name=f"Terneo {self._host}", manufacturer="Terneo")

    @property
    def native_value(self) -> Any:
        return self.coordinator.data.get(self._key)
