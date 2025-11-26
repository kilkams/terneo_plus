from __future__ import annotations

import logging

from homeassistant.components.climate import ClimateEntity, ClimateEntityFeature, HVACMode
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.const import UnitOfTemperature
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN, PAR_TARGET_TEMP
from .api import TerneoApi, CannotConnect
from .coordinator import TerneoCoordinator

_LOGGER = logging.getLogger(__name__)

MODE_MAP = {
    0: HVACMode.OFF,
    1: HVACMode.AUTO,
    3: HVACMode.HEAT,
}
REVERSE_MODE_MAP = {v: k for k, v in MODE_MAP.items()}


class TerneoClimate(CoordinatorEntity, ClimateEntity):
    """Climate entity backed by TerneoCoordinator."""

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.HVAC_MODE
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT, HVACMode.AUTO]

    def __init__(self, coordinator: TerneoCoordinator, api: TerneoApi, host: str):
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.api = api
        self._host = host
        self._attr_name = f"Terneo {host}"

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._host)},
            name=f"Terneo {self._host}",
            manufacturer="Terneo",
        )

    @property
    def available(self) -> bool:
        return super().available

    @property
    def current_temperature(self):
        return self.coordinator.data.get("temp_air")

    @property
    def target_temperature(self):
        return self.coordinator.data.get("target_temp")

    @property
    def hvac_mode(self):
        mode = self.coordinator.data.get("mode")
        return MODE_MAP.get(mode, HVACMode.OFF)

    async def async_set_temperature(self, **kwargs) -> None:
        temperature = kwargs.get("temperature")
        if temperature is None:
            return
        # par.31 expects integer Celsius (device uses int degrees)
        try:
            await self.api.set_parameter(PAR_TARGET_TEMP, int(temperature))
            # request coordinator refresh
            await self.coordinator.async_request_refresh()
        except CannotConnect:
            _LOGGER.error("Cannot connect to device to set temperature")

    async def async_set_hvac_mode(self, hvac_mode: str) -> None:
        mode_code = REVERSE_MODE_MAP.get(hvac_mode)
        if mode_code is None:
            _LOGGER.error("Unsupported HVAC mode %s", hvac_mode)
            return
        try:
            await self.api.set_mode(mode_code)
            await self.coordinator.async_request_refresh()
        except CannotConnect:
            _LOGGER.error("Cannot connect to device to set mode")
