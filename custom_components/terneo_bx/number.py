from __future__ import annotations
import logging
import asyncio
from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import DeviceInfo
from .const import DOMAIN
from .api import TerneoApi, CannotConnect
from .coordinator import TerneoCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Terneo number entities."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: TerneoCoordinator = data["coordinator"]
    api: TerneoApi = data["api"]
    host = entry.data.get("host")
    serial = coordinator.serial

    numbers = [
        TerneoBrightnessNumber(coordinator, api, host, serial),
    ]

    async_add_entities(numbers, update_before_add=True)


class TerneoBrightnessNumber(CoordinatorEntity, NumberEntity):
    """Number entity для управления яркостью дисплея."""
    
    _attr_native_min_value = 0
    _attr_native_max_value = 9
    _attr_native_step = 1
    _attr_mode = NumberMode.SLIDER
    _attr_icon = "mdi:brightness-6"

    def __init__(self, coordinator: TerneoCoordinator, api: TerneoApi, host: str, serial: str):
        super().__init__(coordinator)
        self.api = api
        self._host = host
        self._serial = serial
        self._attr_unique_id = f"terneo_{serial}_brightness"
        self._attr_has_entity_name = True        
        self._attr_translation_key = "brightness"

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._host)},
            name=f"Terneo {self._host}",
            manufacturer="Terneo",
            model="Terneo BX"
        )

    @property
    def native_value(self):
        """Возвращает текущую яркость (0-9)."""
        params_dict = self.coordinator.data.get("params_dict", {})
        brightness_raw = params_dict.get(23)
        
        if brightness_raw is None:
            return None
        
        try:
            return int(brightness_raw)
        except (ValueError, TypeError):
            return None

    async def async_set_native_value(self, value: float) -> None:
        """Установить новое значение яркости."""
        try:
            brightness = int(value)
            _LOGGER.debug(f"Setting brightness to {brightness}")
            
            # ID=23, type=2 (uint8)
            await self.api.set_parameter(23, brightness, self._serial)
            
            # Небольшая задержка для применения изменений
            await asyncio.sleep(self.coordinator.calc_delay())
            
            # Обновляем данные
            await self.coordinator.async_refresh()
            
        except CannotConnect as e:
            _LOGGER.error(f"Cannot connect to set brightness: {e}")
        except Exception as e:
            _LOGGER.error(f"Error setting brightness: {e}", exc_info=True)