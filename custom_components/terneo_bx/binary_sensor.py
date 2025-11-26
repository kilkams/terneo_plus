from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN, CONF_HOST
from .coordinator import TerneoDataUpdateCoordinator


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities):
    coordinator: TerneoDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities([
        TerneoHeatingBinarySensor(coordinator, entry.data[CONF_HOST])
    ])


class TerneoHeatingBinarySensor(BinarySensorEntity):
    _attr_name = "Heating"
    _attr_icon = "mdi:radiator"
    _attr_device_class = "heat"

    def __init__(self, coordinator, host):
        self.coordinator = coordinator
        self._host = host
        self._attr_unique_id = f"terneo_{host}_heating"

    @property
    def is_on(self) -> bool:
        tele = self.coordinator.data.get("telemetry", {})
        load = tele.get("f.0", "0")
        return load == "1"

    @property
    def extra_state_attributes(self):
        return {
            "telemetry": self.coordinator.data.get("telemetry", {})
        }

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._host)},
            name=f"Terneo {self._host}",
            manufacturer="Terneo",
        )

