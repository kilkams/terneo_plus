from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.entity import DeviceInfo
from .const import DOMAIN

class TerneoRawPowerSensor(SensorEntity):
    def __init__(self, coordinator, host):
        self.coordinator = coordinator
        self._host = host
        self._attr_name = f"Terneo {host} Power"
        self._attr_unique_id = f"terneo_{host}_power"
        self._attr_native_unit_of_measurement = "W"

    @property
    def native_value(self):
        data = self.coordinator.data or {}
        raw = data.get("raw") or {}
        par = raw.get("par", [])
        tele = (data.get("telemetry", {}) or {}).get("f.0", [0])
        relay = int(tele[0]) if tele else 0

        enc = 0
        for item in par:
            try:
                if item[0] == 17:
                    enc = int(item[2])
                    break
            except Exception:
                continue

        if enc <= 1500:
            power = enc * 10
        else:
            power = (enc - 1500) * 20

        return power if relay == 1 else 0

    @property
    def device_info(self):
        return DeviceInfo(identifiers={(DOMAIN, self._host)}, name=f"Terneo {self._host}")

class TerneoWifiSignalSensor(SensorEntity):
    """Wi-Fi RSSI/level sensor (o.0 parameter)"""
    def __init__(self, coordinator, host):
        self.coordinator = coordinator
        self._host = host
        self._attr_name = f"Terneo {host} WiFi RSSI"
        self._attr_unique_id = f"terneo_{host}_wifi_rssi"
        self._attr_native_unit_of_measurement = "dBm"

    @property
    def native_value(self):
        tele = self.coordinator.data.get("telemetry", {}) or {}
        val = tele.get("o.0")
        if val is not None:
            try:
                return int(val)
            except Exception:
                pass
        return None

    @property
    def device_info(self):
        return DeviceInfo(identifiers={(DOMAIN, self._host)}, name=f"Terneo {self._host}")
