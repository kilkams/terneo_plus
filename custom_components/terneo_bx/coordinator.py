from __future__ import annotations
import logging
from datetime import timedelta
from typing import Any
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from .api import TerneoApi, CannotConnect

_LOGGER = logging.getLogger(__name__)

class TerneoCoordinator(DataUpdateCoordinator):
    def __init__(self, hass: HomeAssistant, api: TerneoApi, update_interval: timedelta):
        super().__init__(hass, _LOGGER, name='terneo_coordinator', update_interval=update_interval)
        self.api = api
        self.serial = None

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            telemetry = await self.api.get_telemetry()
            # Telemetry is optional on some models — skip if missing
            telemetry = data.get("tl", {})

            return {
                "params": data.get("params", {}),
                "telemetry": telemetry,
                "tt": data.get("tt", {}),
            }
            params = await self.api.get_params()
            if params is None:
                raise UpdateFailed('no params')
            schedule = await self.api.get_schedule()
            sn = telemetry.get('sn') or params.get('sn')
            if sn:
                self.serial = sn
                self.api.sn = sn
            data = {}
            t0 = self.api.extract_int(telemetry, 't.0')
            if t0 is not None:
                data['temp_air'] = t0/10.0
            t1 = self.api.extract_int(telemetry, 't.1')
            if t1 is not None:
                data['temp_floor'] = t1/10.0
            t5 = self.api.extract_int(telemetry, 't.5')
            if t5 is not None:
                data['temp_internal'] = t5/10.0
            target = self.api.extract_param(params, 31)
            if target is not None:
                try:
                    data['target_temp'] = int(target)
                except:
                    data['target_temp'] = None
            else:
                data['target_temp'] = None
            mode = telemetry.get('m.1')
            try:
                data['mode'] = int(mode) if mode is not None else None
            except:
                data['mode'] = None
            f0 = telemetry.get('f.0')
            f10 = telemetry.get('f.10')
            try:
                if f0 is not None:
                    data['relay'] = int(f0)
                elif f10 is not None:
                    data['relay'] = int(f10)
                else:
                    data['relay'] = 0
            except:
                data['relay'] = 0
            enc = self.api.extract_param(params, 17) or 0
            try:
                enc_val = int(enc)
            except:
                enc_val = 0
            if enc_val <= 1500:
                power_w = enc_val * 10
            else:
                power_w = (enc_val - 1500) * 20
            data['power_w'] = power_w if data.get('relay',0)==1 else 0
            wifi = self.api.extract_int(telemetry, 'o.0')
            data['wifi_rssi'] = wifi
            data['raw_telemetry'] = telemetry
            data['raw_params'] = params
            data['schedule'] = schedule.get('tt') if isinstance(schedule, dict) else schedule
            return data
        except CannotConnect as e:
            raise UpdateFailed(e)
        except Exception as e:
            _LOGGER.exception('Error fetching Terneo data: %s', e)
            raise UpdateFailed(e)
