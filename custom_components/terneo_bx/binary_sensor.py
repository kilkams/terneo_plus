from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorDeviceClass
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN
from .coordinator import TerneoCoordinator

# mapping simple convenience sensors
BINARY_DEFS = [
    ("relay", "Heating Active", BinarySensorDeviceClass.HEAT),
    ("wifi_rssi", "WiFi Weak", BinarySensorDeviceClass.CONNECTIVITY),  # we will interpret low RSSI as 'on'
]


async def async_setup_entry(hass, entry, async_add_entities):
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: TerneoCoordinator = data["coordinator"]
    host = entry.data["host"]

    entities = [
        TerneoRelaySensor(coordinator, host),
        TerneoWifiWeakSensor(coordinator, host),
    ]
    async_add_entities(entities)


class TerneoBaseBinary(CoordinatorEntity, BinarySensorEntity):
    def __init__(self, coordinator: TerneoCoordinator, host: str):
        super().__init__(coordinator)
        self._host = host

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(identifiers={(DOMAIN, self._host)}, name=f"Terneo {self._host}", manufacturer="Terneo")


class TerneoRelaySensor(TerneoBaseBinary):
    def __init__(self, coordinator: TerneoCoordinator, host: str):
        super().__init__(coordinator, host)
        self._attr_name = f"Terneo {host} Heating Active"
        self._attr_unique_id = f"terneo_{host}_heating"
        self._attr_device_class = BinarySensorDeviceClass.HEAT

    @property
    def is_on(self) -> bool:
        val = self.coordinator.data.get("relay", 0)
        try:
            return int(val) == 1
        except Exception:
            return False


class TerneoWifiWeakSensor(TerneoBaseBinary):
    def __init__(self, coordinator: TerneoCoordinator, host: str):
        super().__init__(coordinator, host)
        self._attr_name = f"Terneo {host} WiFi Weak"
        self._attr_unique_id = f"terneo_{host}_wifi_weak"
        self._attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    @property
    def is_on(self) -> bool:
        rssi = self.coordinator.data.get("wifi_rssi")
        try:
            if rssi is None:
                return False
            return int(rssi) < -70
        except Exception:
            return False
