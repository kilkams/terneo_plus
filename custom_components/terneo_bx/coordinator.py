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
        self.serial = serial

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

        # Преобразуем структуру Terneo BX → нормальная
        try:
            # Температура воздуха (t.0) - делим на 10 для получения градусов
            temp_air = int(telemetry.get("t.0", 0)) / 10 if telemetry.get("t.0") else None
            
            # Температура пола (t.1) - делим на 10
            temp_floor = int(telemetry.get("t.1", 0)) / 10 if telemetry.get("t.1") else None
            
            # Дополнительный датчик температуры (t.5) - если нужен
            temp_external = int(telemetry.get("t.5", 0)) / 10 if telemetry.get("t.5") else None
            
            # Статус реле (m.2) - любое значение > 0 означает включено
            raw_pwr = telemetry.get("m.2")
            power = 1 if (raw_pwr is not None and int(raw_pwr) > 0) else 0

        except (ValueError, TypeError) as e:
            raise UpdateFailed(f"Invalid telemetry payload: {e}")

        # Разбор параметров
        try:
            target_temp = par[2]  # целевая температура
            mode = par[17]  # режим отопления
        except (IndexError, TypeError) as e:
            raise UpdateFailed(f"Params structure mismatch: {e}")

        # Итоговые данные
        return {
            "temp_air": temp_air,
            "temp_floor": temp_floor,
            "temp_external": temp_external,  # дополнительный датчик
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