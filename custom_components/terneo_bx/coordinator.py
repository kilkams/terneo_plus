from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import TerneoApi
from .const import PAR_TARGET_TEMP

_LOGGER = logging.getLogger(__name__)


class TerneoCoordinator(DataUpdateCoordinator):
    """Coordinator to fetch Terneo telemetry + params periodically."""

    def __init__(self, hass: HomeAssistant, api: TerneoApi, update_interval: timedelta):
        super().__init__(
            hass,
            _LOGGER,
            name="terneo_coordinator",
            update_interval=update_interval,
        )
        self.api = api

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from device and return normalized dict used by entities."""
        try:
            telemetry = await self.api.get_telemetry()
            if telemetry is None:
                raise UpdateFailed("No telemetry response")

            params = await self.api.get_params()
            if params is None:
                raise UpdateFailed("No params response")

            data: dict[str, Any] = {}

            # temperatures (telemetry returns ints scaled by 10)
            t0 = self.api.extract_int(telemetry, "t.0")
            if t0 is not None:
                data["temp_air"] = t0 / 10.0

            t1 = self.api.extract_int(telemetry, "t.1")
            if t1 is not None:
                data["temp_floor"] = t1 / 10.0

            # sometimes setpoint in telemetry t.5 (x10)
            t5 = self.api.extract_int(telemetry, "t.5")
            if t5 is not None:
                data["temp_internal"] = t5 / 10.0

            # target temperature from params (par.31)
            target_raw = self.api.extract_param(params, PAR_TARGET_TEMP)
            if target_raw is not None:
                try:
                    data["target_temp"] = int(target_raw)
                except Exception:
                    data["target_temp"] = None
            else:
                data["target_temp"] = None

            # mode (m.1)
            m1 = telemetry.get("m.1")
            try:
                data["mode"] = int(m1) if m1 is not None else None
            except Exception:
                data["mode"] = None

            # relay state f.0 or f.10 (some devices)
            # prefer f.0, then f.10
            try:
                f0 = telemetry.get("f.0")
                f10 = telemetry.get("f.10")
                if f0 is not None:
                    data["relay"] = int(f0)
                elif f10 is not None:
                    data["relay"] = int(f10)
                else:
                    data["relay"] = 0
            except Exception:
                data["relay"] = 0

            # power encoded in params par.17 (if present)
            enc = self.api.extract_param(params, 17)
            try:
                enc_val = int(enc) if enc is not None else 0
            except Exception:
                enc_val = 0

            if enc_val <= 1500:
                power_w = enc_val * 10
            else:
                power_w = (enc_val - 1500) * 20

            if data.get("relay", 0) == 1:
                data["power_w"] = power_w
            else:
                data["power_w"] = 0

            # WiFi
            wifi = self.api.extract_int(telemetry, "o.0")
            data["wifi_rssi"] = wifi

            # raw pass-through
            data["raw_telemetry"] = telemetry
            data["raw_params"] = params

            return data

        except UpdateFailed:
            raise
        except Exception as err:
            _LOGGER.exception("Error fetching Terneo data: %s", err)
            raise UpdateFailed(err)
