from __future__ import annotations
import logging
from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.const import UnitOfTemperature
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN, PAR_TARGET_TEMP
from .api import TerneoApi, CannotConnect
from .coordinator import TerneoCoordinator

_LOGGER = logging.getLogger(__name__)

# соответствие кодов тернео → HA
MODE_MAP = {
    0: HVACMode.OFF,
    3: HVACMode.HEAT,   # реальный рабочий режим
}

# обратное соответствие
REVERSE_MODE_MAP = {v: k for k, v in MODE_MAP.items()}


async def async_setup_entry(hass, entry, async_add_entities):
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: TerneoCoordinator = data["coordinator"]
    api: TerneoApi = data["api"]

    async_add_entities([
        TerneoClimate(
            coordinator=coordinator,
            api=api
        )
    ], True)


class TerneoClimate(CoordinatorEntity, ClimateEntity):
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT]

    def __init__(self, coordinator: TerneoCoordinator, api: TerneoApi):
        super().__init__(coordinator)
        self.api = api
        self._host = coordinator.host
        self._serial = coordinator.serial

        self._attr_name = f"Terneo {self._host}"
        self._attr_unique_id = f"{DOMAIN}_{self._serial}"

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._serial)},
            name=f"Terneo {self._host}",
            manufacturer="Terneo",
            model="Terneo BX"
        )

    @property
    def current_temperature(self):
        return self.coordinator.data.get("temp_air")

    @property
    def target_temperature(self):
        return self.coordinator.data.get("target_temp")

    @property
    def hvac_mode(self):
        return MODE_MAP.get(self.coordinator.data.get("mode"), HVACMode.OFF)

    async def async_set_temperature(self, **kwargs):
        temperature = kwargs.get("temperature")
        if temperature is None:
            return
        try:
            await self.api.set_parameter(
                PAR_TARGET_TEMP,
                int(temperature),
                sn=self._serial
            )
            await self.coordinator.async_request_refresh()
        except CannotConnect:
            _LOGGER.error("Cannot connect to set temperature")

    async def async_set_hvac_mode(self, hvac_mode):
        mode_code = REVERSE_MODE_MAP.get(hvac_mode)
        if mode_code is None:
            _LOGGER.error("Unsupported HVAC mode %s", hvac_mode)
            return

        try:
            # параметр 17 — режим работы
            await self.api.set_parameter(
                17,
                mode_code,
                sn=self._serial
            )
            await self.coordinator.async_request_refresh()
        except CannotConnect:
            _LOGGER.error("Cannot connect to set mode")
