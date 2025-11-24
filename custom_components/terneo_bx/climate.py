from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    HVAC_MODE_HEAT, HVAC_MODE_OFF, SUPPORT_TARGET_TEMPERATURE
)
from homeassistant.const import TEMP_CELSIUS
from homeassistant.helpers.entity import DeviceInfo
from .const import DOMAIN

class TerneoClimate(ClimateEntity):
    def __init__(self, coordinator, host):
        self.coordinator = coordinator
        self._host = host
        self._attr_name = f"Terneo {host}"
        self._attr_unique_id = f"terneo_{host}_climate"
        self._attr_supported_features = SUPPORT_TARGET_TEMPERATURE
        self._attr_temperature_unit = TEMP_CELSIUS

    @property
    def hvac_mode(self):
        tele = (self.coordinator.data.get("telemetry", {}) or {})
        return HVAC_MODE_HEAT if str(tele.get("f.0", [0])[0]) == "1" else HVAC_MODE_OFF

    @property
    def current_temperature(self):
        tele = (self.coordinator.data.get("telemetry", {}) or {})
        for k, v in tele.items():
            if k.startswith("t") and isinstance(v, (int, float, str)):
                try:
                    return float(v) / 16.0
                except Exception:
                    continue
        raw = (self.coordinator.data.get("raw", {}) or {})
        for p in raw.get("par", []):
            if p[0] == 1:
                try:
                    return float(p[2])
                except Exception:
                    pass
        return None

    @property
    def target_temperature(self):
        tele = (self.coordinator.data.get("telemetry", {}) or {})
        if "t.5" in tele:
            try:
                return float(tele.get("t.5")) / 16.0
            except Exception:
                pass
        raw = (self.coordinator.data.get("raw", {}) or {})
        for p in raw.get("par", []):
            if p[0] == 31:
                try:
                    return float(p[2])
                except Exception:
                    pass
        return None

    async def async_set_temperature(self, **kwargs):
        if "temperature" in kwargs:
            temp = kwargs["temperature"]
            sn = self.coordinator.sn
            if sn is None:
                return
            await self.coordinator.api.set_temperature(temp, sn)
            await self.coordinator.async_request_refresh()

    @property
    def device_info(self):
        return DeviceInfo(identifiers={(DOMAIN, self._host)}, name=f"Terneo {self._host}")

    @property
    def extra_state_attributes(self):
        data = self.coordinator.data or {}
        schedule = (data.get("schedule") or {}).get("tt")
        return {"schedule": schedule}
