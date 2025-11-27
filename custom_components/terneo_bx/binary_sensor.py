from __future__ import annotations
from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorDeviceClass
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import DeviceInfo
from .const import DOMAIN
from .coordinator import TerneoCoordinator

BINARY_DEFS = [
    ('relay','Heating Active', BinarySensorDeviceClass.HEAT),
]

async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]['coordinator']
    host = entry.data.get('host')
    entities = [TerneoRelaySensor(coordinator, host)]
    async_add_entities(entities)

class TerneoRelaySensor(CoordinatorEntity, BinarySensorEntity):
    def __init__(self, coordinator: TerneoCoordinator, host: str):
        super().__init__(coordinator)
        self._host = host
        self._attr_name = f"Terneo {host} Heating Active"
        self._attr_unique_id = f"terneo_{host}_heating_active"
        self._attr_device_class = BinarySensorDeviceClass.HEAT

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(identifiers={(DOMAIN, self._host)}, name=f"Terneo {self._host}", manufacturer="Terneo", model="Terneo BX")

    @property
    def is_on(self) -> bool:
        val = self.coordinator.data.get('relay',0)
        try:
            return int(val) == 1
        except:
            return False
