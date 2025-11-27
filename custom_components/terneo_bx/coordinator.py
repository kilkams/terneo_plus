from datetime import timedelta
import logging

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)


class TerneoCoordinator(DataUpdateCoordinator):
    """Coordinator for Terneo BX."""

    def __init__(self, hass, api, update_interval, serial):
        super().__init__(
            hass,
            _LOGGER,
            name="Terneo BX Coordinator",
            update_interval=update_interval,
        )
        self.api = api
        self.serial = serial   # ← добавлено

    async def _async_update_data(self):
        """Fetch full Terneo state."""

        # 1) Параметры
        try:
            params = await self.api.get_params()
        except Exception as e:
            raise UpdateFailed(f"Failed to read params: {e}")

        par = params.get("par")
        if not isinstance(par, list):
            raise UpdateFailed("Invalid params payload")

        # 2) Расписание
        try:
            schedule = await self.api.get_schedule()
        except Exception as e:
            raise UpdateFailed(f"Failed to read schedule: {e}")

        tt = schedule.get("tt")
        if not isinstance(tt, dict):
            raise UpdateFailed("Invalid schedule payload")

        # 3) Время
        try:
            time_data = await self.api.get_time()
        except Exception as e:
            raise UpdateFailed(f"Failed to read time: {e}")

        # 4) Телеметрия
        try:
            telemetry = await self.api.get_telemetry()
        except Exception as e:
            raise UpdateFailed(f"Failed to read telemetry: {e}")

        tl = telemetry.get("tl")
        if not isinstance(tl, dict):
            raise UpdateFailed("Invalid telemetry payload")

        # Разбор телеметрии
        temp_air = tl.get("0")
        temp_floor = tl.get("1")
        power = tl.get("pwr")

        # Разбор параметров
        try:
            target_temp = par[2]
            mode = par[17]  # режим отопления
        except Exception:
            raise UpdateFailed("Params structure mismatch")

        # Итоговые данные
        return {
            "temp_air": temp_air,
            "temp_floor": temp_floor,
            "power": power,
            "target_temp": target_temp,
            "mode": mode,
            "schedule": tt,
            "time": time_data.get("time") if time_data else None,
            "raw": {
                "params": params,
                "telemetry": telemetry,
            },
        }
