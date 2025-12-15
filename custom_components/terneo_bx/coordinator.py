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
        self._cached_time = {}
        self._schedule_update_counter = 5
        self._time_update_counter = 20   

        self._min_delay = 0.2   # минимальная задержка в секундах
        self._max_delay = 5.0   # максимальная задержка
        self._delay_multiplier = 1.4 # коэффициент задержки

 
    async def _async_update_data(self):
        """Fetch full Terneo state."""
        
        # Сохраняем предыдущие данные для fallback
        previous_data = self.data if self.data else {}

        # 1) Параметры (критичные данные)
        try:
            params = await self.api.get_params()
            par = params.get("par")
            if not isinstance(par, list):
                raise UpdateFailed("Invalid params payload - not a list")
        except Exception as e:
            _LOGGER.error(f"Failed to read params: {e}")
            # Если есть предыдущие данные, используем их
            if previous_data.get("raw", {}).get("params"):
                _LOGGER.warning("Using previous params data")
                par = previous_data["raw"]["params"].get("par", [])
            else:
                raise UpdateFailed(f"Failed to read params and no cached data: {e}")

        await asyncio.sleep(self.calc_delay())
  
        # 2) Время (некритичные данные)
        if self._time_update_counter >= 20:        
            try:
                time_data = await self.api.get_time()
                if time_data:
                    self._cached_time = time_data
                    self._time_update_counter = 0
                else:
                    _LOGGER.warning("Empty time data received, keeping cache")
            except Exception as e:
                _LOGGER.error(f"Failed to read time: {e}")
            finally:
                self._time_update_counter = 0
            await asyncio.sleep(self.calc_delay())               
        else:
            self._time_update_counter += 1
        
        # Используем кэшированное значение
        time_data = self._cached_time

        # 3) Телеметрия (критичные данные)
        try:
            telemetry = await self.api.get_telemetry()
            if not telemetry:
                raise UpdateFailed("Empty telemetry data")
        except Exception as e:
            _LOGGER.error(f"Failed to read telemetry: {e}")
            # Пробуем использовать предыдущие данные
            if previous_data.get("raw", {}).get("telemetry"):
                _LOGGER.warning("Using previous telemetry data")
                telemetry = previous_data["raw"]["telemetry"]
            else:
                raise UpdateFailed(f"Failed to read telemetry and no cached data: {e}")
        
        await asyncio.sleep(self.calc_delay())

        # 4) Расписание (некритичные данные)
        if self._schedule_update_counter >= 5: 
            try:
                schedule = await self.api.get_schedule()
                tt = schedule.get("tt")
                if isinstance(tt, dict) and tt:
                    self._cached_schedule = tt
                    self._schedule_update_counter = 0
                else:
                    _LOGGER.warning("Invalid schedule data, keeping cache")
            except Exception as e:
                _LOGGER.error(f"Failed to read schedule: {e}")
            finally:
                self._schedule_update_counter = 0
        else:
            self._schedule_update_counter += 1
        
        # Используем кэшированное расписание
        tt = self._cached_schedule

        # Преобразуем структуру Terneo BX → нормальная
        try:
            # Температура воздуха (t.0) - делим на 16 для получения градусов
            temp_air_raw = telemetry.get("t.0")
            temp_air = round((int(temp_air_raw) / 16), 2) if temp_air_raw is not None else None
            
            # Температура пола (t.1) - делим на 16
            temp_floor_raw = telemetry.get("t.1")
            temp_floor = round((int(temp_floor_raw) / 16), 2) if temp_floor_raw is not None else None
            
            # Дополнительный датчик температуры (t.5)
            temp_external_raw = telemetry.get("t.5")
            temp_external = round((int(temp_external_raw) / 16), 2) if temp_external_raw is not None else None
            
            # Статус реле (f.0) - любое значение > 0 означает включено
            raw_pwr = telemetry.get("f.0")
            power = int(raw_pwr) if raw_pwr is not None else 0

            # Уровень сигнала WiFi (o.0)
            wifi_rssi_raw = telemetry.get("o.0")
            wifi_rssi = int(wifi_rssi_raw) if wifi_rssi_raw is not None else None

        except (ValueError, TypeError) as e:
            _LOGGER.error(f"Invalid telemetry payload: {e}")
            raise UpdateFailed(f"Invalid telemetry payload: {e}")
 
        # Разбор параметров - создаем словарь {id: value}
        params_dict = {}
        try:
            for item in par:
                if len(item) >= 3:
                    param_id = item[0]
                    param_value = item[2]
                    params_dict[param_id] = param_value
            
            # Проверяем наличие критичных параметров
            if not params_dict:
                raise ValueError("Empty params_dict")
            
            # ID=31: setTemperature - температура уставки текущего режима
            target_temp_raw = params_dict.get(31)
            target_temp = int(target_temp_raw) if target_temp_raw is not None else None
            
            # ID=2: mode - режим работы (0=расписание, 1=ручной)
            mode_raw = params_dict.get(2)
            mode = int(mode_raw) if mode_raw is not None else 0
            
            # ID=3: controlType - режим контроля (0=по полу, 1=по воздуху, 2=расширенный)
            control_type_raw = params_dict.get(3)
            control_type = int(control_type_raw) if control_type_raw is not None else None
            
            # ID=4: manualAir - уставка ручного режима по воздуху
            manual_air_raw = params_dict.get(4)
            manual_air = int(manual_air_raw) if manual_air_raw is not None else None
            
            # ID=5: manualFloorTemperature - уставка ручного режима по полу
            manual_floor_raw = params_dict.get(5)
            manual_floor = int(manual_floor_raw) if manual_floor_raw is not None else None
            
            # ID=17: power - нагрузка
            power_w_raw = params_dict.get(17)
            if power_w_raw is not None:
                power_w_int = int(power_w_raw)
                if power_w_int <= 150:                
                    power_w = power_w_int * 10 
                else:
                    power_w = 1500 + (power_w_int * 20)
            else: 
                power_w = None    

            # ID=19: histeresis - гистерезис в 1/10 °C
            histeresis_raw = params_dict.get(19)
            histeresis = int(histeresis_raw) / 10 if histeresis_raw is not None else None
            
            # ID=125: powerOff - выключение устройства
            power_off_raw = params_dict.get(125)
            power_off = int(power_off_raw) if power_off_raw is not None else 0
            
            # ID=118: coolingControlWay - режим нагрев(0) или охлаждение(1)
            hvac_mode_raw = params_dict.get(118)
            hvac_mode = int(hvac_mode_raw) if hvac_mode_raw is not None else 0

            # ID=23: brightness - яркость экрана (0-9)
            brightness_raw = params_dict.get(23)
            brightness = int(brightness_raw) if brightness_raw is not None else None

        except (ValueError, TypeError, KeyError) as e:
            _LOGGER.error(f"Params parsing error: {e}")
            raise UpdateFailed(f"Params parsing error: {e}")
 
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
                "params": {"par": par},
                "telemetry": telemetry,
            },
        }

    def calc_delay(self):
        dur = self.api.last_request_duration
        if not dur:
            return 1.0
        delay = max(self._min_delay, min(self._max_delay, (dur / 1000) * self._delay_multiplier))
        return delay
        