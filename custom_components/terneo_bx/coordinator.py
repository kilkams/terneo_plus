import logging
from datetime import timedelta
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed
)

from .const import (
    PAR_TARGET_TEMP,
)

_LOGGER = logging.getLogger(__name__)


class TerneoCoordinator(DataUpdateCoordinator):
    """Coordinator that fetches telemetry + params."""

    def __init__(self, hass, api, update_interval: timedelta):
        super().__init__(
            hass,
            _LOGGER,
            name="terneo_coordinator",
            update_interval=update_interval,
        )
        self.api = api

    async def _async_update_data(self):
        """Fetch data from Terneo device."""
        telemetry = await self.api.get_telemetry()
        if telemetry is None:
            raise UpdateFailed("Cannot connect (telemetry)")

        params = await self.api.get_params()
        if params is None:
            raise UpdateFailed("Cannot connect (params)")

        data = {}

        # -----------------------------------------------------------
        # TEMPERATURE SENSORS
        # -----------------------------------------------------------
        # t.0 — air temp (×10)
        t0 = self.api.extract_int(telemetry, "t.0")
        if t0 is not None:
            data["temp_air"] = t0 / 10.0

        # t.1 — floor temp (×10)
        t1 = self.api.extract_int(telemetry, "t.1")
        if t1 is not None:
            data["temp_floor"] = t1 / 10.0

        # t.5 — setpoint (sometimes)
        t5 = self.api.extract_int(telemetry, "t.5")
        if t5 is not None:
            data["temp_internal"] = t5 / 10.0

        # -----------------------------------------------------------
        # TARGET TEMPERATURE (PAR 31)
        # -----------------------------------------------------------
        target_raw = self.api.extract_param(params, PAR_TARGET_TEMP)
        if target_raw is not None:
            # par.31 — integer Celsius
            try:
                data["target_temp"] = int(target_raw)
            except:
                data["target_temp"] = None
        else:
            data["target_temp"] = None

        # -----------------------------------------------------------
        # HEATING MODE (m.1)
        # -----------------------------------------------------------
        mode = telemetry.get("m.1")
        if mode is not None:
            try:
                data["mode"] = int(mode)
            except:
                data["mode"] = None

        # -----------------------------------------------------------
        # WIFI SIGNAL (o.0)
        # -----------------------------------------------------------
        wifi = telemetry.get("o.0")
        try:
            data["wifi_signal"] = int(wifi)
        except:
            data["wifi_signal"] = None

        # Raw response also included
        data["raw_telemetry"] = telemetry
        data["raw_params"] = params

        return data
