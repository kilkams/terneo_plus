from datetime import timedelta
import logging, asyncio

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)


class TerneoCoordinator(DataUpdateCoordinator):
    """Coordinator for Terneo BX."""

    def __init__(self, hass, api, update_interval, serial, host):
        super().__init__(
            hass,
            _LOGGER,
            name="Terneo BX Coordinator",
            update_interval=update_interval,
        )
        self.api = api
        self.serial = serial
        self.host = host

        # Кэш для редко меняющихся данных
        self._cached_schedule = {}
        self._cached_params = []
        self._schedule_update_counter = 5
        self._time_update_counter = 20        

    async def _async_update_data(self):
        """Fetch full Terneo state."""

        # 1) Параметры
        try:
            params = await self.api.get_params()
            par = params.get("par")
            if not isinstance(par, list):
                _LOGGER.warning("Invalid params payload, using empty list")
                par = []
        except Exception as e:
            _LOGGER.error(f"Failed to read params: {e}")
            par = []

        await asyncio.sleep(1)

        # 2) Телеметрия
        try:
            telemetry = await self.api.get_telemetry()
        except Exception as e:
            raise UpdateFailed(f"Failed to read telemetry: {e}")
        
        await asyncio.sleep(1)

        # 3) Расписание
        try:
            schedule = await self.api.get_schedule()
            tt = schedule.get("tt")
            if not isinstance(tt, dict):
                _LOGGER.warning("Invalid schedule payload, using empty dict")
                tt = {}
        except Exception as e:
            _LOGGER.error(f"Failed to read schedule: {e}")
            tt = {}

        await asyncio.sleep(1)

        # 4) Время
        if self._time_update_counter >= 20:        
            try:
                time_data = await self.api.get_time()
                self._time_update_counter = 0
            except Exception as e:
                _LOGGER.error(f"Failed to read time: {e}")
                time_data = {}
        else:
            self._time_update_counter += 1
        # Преобразуем структуру Terneo BX → нормальная
        try:
            # Температура воздуха (t.0) - делим на 10 для получения градусов
            temp_air = round((int(telemetry.get("t.0", 0)) / 16), 2) if telemetry.get("t.0") else None
            
            # Температура пола (t.1) - делим на 10
            temp_floor = round((int(telemetry.get("t.1", 0)) / 16), 2) if telemetry.get("t.1") else None
            
            # Дополнительный датчик температуры (t.5) - если нужен
            temp_external = round((int(telemetry.get("t.5", 0)) / 16), 2) if telemetry.get("t.5") else None
            
            # Статус реле (f.0) - любое значение > 0 означает включено
            raw_pwr = telemetry.get("f.0")
            power = int(raw_pwr) if raw_pwr else 0

            # Уровень сигнала WiFi (o.0) - если нужен
            wifi_rssi = int(telemetry.get("o.0", 0)) if telemetry.get("o.0") else None

        except (ValueError, TypeError) as e:
            raise UpdateFailed(f"Invalid telemetry payload: {e}")
 
        # Разбор параметров - создаем словарь {id: value}
        params_dict = {}
        try:
            for item in par:
                if len(item) >= 3:
                    param_id = item[0]
                    param_value = item[2]
                    params_dict[param_id] = param_value
            
            # ID=31: setTemperature - температура уставки текущего режима
            target_temp_raw = params_dict.get(31)
            target_temp = int(target_temp_raw) if target_temp_raw else None
            
            # ID=2: mode - режим работы (0=расписание, 1=ручной)
            mode_raw = params_dict.get(2)
            mode = int(mode_raw) if mode_raw else 0
            
            # ID=3: controlType - режим контроля (0=по полу, 1=по воздуху, 2=расширенный)
            control_type_raw = params_dict.get(3)
            control_type = int(control_type_raw) if control_type_raw else None
            
            # ID=4: manualAir - уставка ручного режима по воздуху
            manual_air_raw = params_dict.get(4)
            manual_air = int(manual_air_raw) if manual_air_raw else None
            
            # ID=5: manualFloorTemperature - уставка ручного режима по полу
            manual_floor_raw = params_dict.get(5)
            manual_floor = int(manual_floor_raw) if manual_floor_raw else None
            
            # ID=17: power - нагрузка
            power_w_raw = params_dict.get(17)
            if int(power_w_raw) <= 150:                
                power_w = int(power_w_raw) * 10 
            elif int(power_w_raw) > 150: 
                power_w = 1500 + (int(power_w_raw) * 20)
            else: 
                power_w = None    

            # ID=19: histeresis - гистерезис в 1/10 °C
            histeresis_raw = params_dict.get(19)
            histeresis = int(histeresis_raw) / 10 if histeresis_raw else None
            
            # ID=125: powerOff - выключение устройства
            power_off_raw = params_dict.get(125)
            power_off = int(power_off_raw) if power_off_raw else 0
            
            # ID=118: coolingControlWay - режим нагрев(0) или охлаждение(1)
            hvac_mode_raw = params_dict.get(118)
            hvac_mode = int(hvac_mode_raw) if hvac_mode_raw else 0

            # ID=23: brightness - яркость экрана (0-9)
            brightness_raw = params_dict.get(23)
            brightness = int(brightness_raw) if brightness_raw else None

        except (ValueError, TypeError, KeyError) as e:
            _LOGGER.error(f"Params parsing error: {e}")
            target_temp = None
            mode = 0
            control_type = None
            manual_air = None
            manual_floor = None
            histeresis = None
            power_off = 0
            hvac_mode = 0
            power_w = None
            brightness = 0            

        # Итоговые данные
        return {
            "temp_air": temp_air,
            "temp_floor": temp_floor,
            "temp_external": temp_external,
            "power": power,
            "power_w": power_w,
            "target_temp": target_temp,
            "mode": mode,
            "control_type": control_type,
            "manual_air": manual_air,
            "manual_floor": manual_floor,
            "histeresis": histeresis,
            "power_off": power_off,
            "hvac_mode": hvac_mode,
            "wifi_rssi": wifi_rssi,
            "schedule": tt,
            "tt": tt,
            "time": time_data.get("time") if time_data else None,
            "params_dict": params_dict,
            "brightness": brightness,
            "raw": {
                "params": params if par else {},
                "telemetry": telemetry,
            },
        }