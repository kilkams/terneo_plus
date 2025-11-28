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

from .const import DOMAIN
from .api import TerneoApi, CannotConnect
from .coordinator import TerneoCoordinator

_LOGGER = logging.getLogger(__name__)

# Правильная карта режимов Terneo
# ID=2 (mode): 0=расписание, 1=ручной
# ID=125 (powerOff): 0=включено, 1=выключено
MODE_MAP = {
    "off": HVACMode.OFF,      # powerOff=1
    "schedule": HVACMode.AUTO,  # mode=0, powerOff=0
    "manual": HVACMode.HEAT,    # mode=1, powerOff=0
}


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
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.AUTO, HVACMode.HEAT]

    def __init__(self, coordinator: TerneoCoordinator, api: TerneoApi):
        super().__init__(coordinator)
        self.api = api
        self._host = coordinator.host
        self._serial = coordinator.serial

        self._attr_name = f"Terneo {self._host}"
        self._attr_unique_id = f"Terneo_{self._host}"

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._host)},
            name=f"Terneo {self._host}",
            manufacturer="Terneo",
            model="Terneo BX"
        )

    @property
    def current_temperature(self):
        return self.coordinator.data.get("temp_floor")

    @property
    def target_temperature(self):
        return self.coordinator.data.get("target_temp")

    @property
    def hvac_mode(self):
        """Определяем текущий режим HVAC."""
        power_off = self.coordinator.data.get("power_off", 0)
        mode = self.coordinator.data.get("mode", 0)
        
        if power_off == 1:
            return HVACMode.OFF
        elif mode == 0:
            return HVACMode.AUTO  # расписание
        else:
            return HVACMode.HEAT  # ручной режим

    async def async_set_temperature(self, **kwargs):
        """Установить целевую температуру."""
        temperature = kwargs.get("temperature")
        if temperature is None:
            return
        
        try:
            # 1. Переключаем в ручной режим обогрева
            power_off = self.coordinator.data.get("power_off", 0)
            current_mode = self.coordinator.data.get("mode", 0)
            
            if power_off == 1 or current_mode == 0:
                await self.api.set_parameter(125, 0, self._serial)  # Включить
                await self.api.set_parameter(2, 1, self._serial)     # Ручной режим
            
            # ID=31 - setTemperature
            await self.api.set_parameter(31, int(temperature), self._serial)
            await self.coordinator.async_refresh()
        except CannotConnect:
            _LOGGER.error("Cannot connect to set temperature")
        except Exception as e:
            _LOGGER.error(f"Error setting temperature: {e}")

    async def async_set_hvac_mode(self, hvac_mode):
        """Установить режим HVAC."""
        _LOGGER.debug(f"Setting HVAC mode to: {hvac_mode}")
        
        try:
            if hvac_mode == HVACMode.OFF:
                # Выключить устройство: ID=125 (powerOff) = 1
                await self.api.set_parameter(125, 1, self._serial)
            elif hvac_mode == HVACMode.AUTO:
                # Режим расписания: ID=2 (mode) = 0, ID=125 (powerOff) = 0
                await self.api.set_parameter(125, 0, self._serial)
                await self.api.set_parameter(2, 0, self._serial)
            elif hvac_mode == HVACMode.HEAT:
                # Ручной режим: ID=2 (mode) = 1, ID=125 (powerOff) = 0
                await self.api.set_parameter(125, 0, self._serial)
                await self.api.set_parameter(2, 1, self._serial)
            else:
                _LOGGER.error(f"Unsupported HVAC mode: {hvac_mode}")
                return
            
            await self.coordinator.async_refresh()
            
        except CannotConnect:
            _LOGGER.error("Cannot connect to set HVAC mode")
        except Exception as e:
            _LOGGER.error(f"Error setting HVAC mode: {e}")