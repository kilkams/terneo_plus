from homeassistant.components.binary_sensor import BinarySensorEntity
from .const import DOMAIN

class TerneoHeatingBinarySensor(BinarySensorEntity):
    def __init__(self, coordinator, host):
        self.coordinator = coordinator
        self._host = host
        self._attr_name = f"Terneo {host} Heating"
        self._attr_unique_id = f"terneo_{host}_heating"

    @property
    def is_on(self):
        tele = (self.coordinator.data.get("telemetry", {}) or {})
        val = tele.get("f.0")
        try:
            if isinstance(val, list):
                return str(val[0]) == "1"
            return str(val) == "1"
        except Exception:
            return False
