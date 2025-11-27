from datetime import timedelta
import logging

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)


class TerneoCoordinator(DataUpdateCoordinator):
    """Coordinator for Terneo BX."""

    def __init__(self, hass, api, update_interval):
        super().__init__(
            hass,
            _LOGGER,
            name="Terneo BX Coordinator",
            update_interval=update_interval,
        )
        self.api = api

    async def _async_update_data(self):
        """Fetch full Terneo state."""

        # 1) Параметры (cmd 1)
        try:
            params = await self.api.get_params()
        except Exception as e:
            raise UpdateFailed(f"Failed to read params: {e}")

        if not params or "par" not in params:
            raise UpdateFailed("Invalid params payload")

        # 2) Расписание (cmd 2)
        try:
            schedule = await self.api.get_schedule()
        except Exception as e:
            raise UpdateFailed(f"Failed to read schedule: {e}")

        if not schedule or "tt" not in schedule:
            raise UpdateFailed("Invalid schedule payload")

        # 3) Время (cmd 3)
        try:
            time_data = await self.api.get_time()
        except Exception as e:
            raise UpdateFailed(f"Failed to read time: {e}")

        # 4) Телеметрия (cmd 4)
        try:
            telemetry = await self.api.get_telemetry()
        except Exception as e:
            raise UpdateFailed(f"Failed to read telemetry: {e}")

        if not telemetry:
            raise UpdateFailed("no telemetry")

        # 5) Собираем данные в один словарь (как любит HA)
        data = {
            "params": params,
            "tt": schedule.get("tt"),
            "time": time_data.get("time") if time_data else None,
            "telemetry": telemetry,
        }

        return data
