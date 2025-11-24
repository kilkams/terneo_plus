from datetime import timedelta
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.core import HomeAssistant
from .api import TerneoAPI
from .const import DEFAULT_SCAN_INTERVAL

class TerneoCoordinator(DataUpdateCoordinator):
    def __init__(self, hass: HomeAssistant, host: str, scan_interval: int = DEFAULT_SCAN_INTERVAL):
        self.api = TerneoAPI(host)
        self._host = host
        super().__init__(
            hass,
            logger=hass.helpers.logger.getLogger("terneo_thermostat"),
            name=f"Terneo {host}",
            update_interval=timedelta(seconds=scan_interval),
        )
        self.sn = None

    async def _async_update_data(self):
        raw = await self.api.get_raw()
        tele = await self.api.get_telemetry()
        if raw and isinstance(raw, dict):
            sn = raw.get("sn") or raw.get("serial")
            if sn:
                self.sn = sn
        schedule = None
        if self.sn:
            try:
                schedule = await self.api.get_schedule(self.sn)
            except Exception:
                schedule = None
        return {
            "raw": raw,
            "telemetry": tele,
            "schedule": schedule,
        }

    async def async_close(self):
        await self.api.close()
