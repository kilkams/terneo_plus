from __future__ import annotations
import logging
from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import DeviceInfo
from .const import DOMAIN
from .api import TerneoApi, CannotConnect
from .coordinator import TerneoCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Terneo switches."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: TerneoCoordinator = data["coordinator"]
    api: TerneoApi = data["api"]
    host = entry.data.get("host")
    serial = coordinator.serial

    switches = [
        TerneoChildLockSwitch(coordinator, api, host, serial),
        TerneoNightBrightnessSwitch(coordinator, api, host, serial),
        TerneoPreheatSwitch(coordinator, api, host, serial),
        TerneoWindowControlSwitch(coordinator, api, host, serial),
    ]

    async_add_entities(switches, update_before_add=True)


class TerneoBaseSwitch(CoordinatorEntity, SwitchEntity):
    """Base class for Terneo switches."""
    _attr_has_entity_name = True
    def __init__(self, coordinator: TerneoCoordinator, api: TerneoApi, host: str, serial: str, param_id: int, translation_key: str, icon: str):
        super().__init__(coordinator)
        self.api = api
        self._host = host
        self._serial = serial
        self._param_id = param_id
        self._attr_translation_key = translation_key
        self._attr_unique_id = f"terneo_{serial}_{name.lower().replace(' ', '_')}"
        self._attr_icon = icon

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._host)},
            name=f"Terneo {self._host}",
            manufacturer="Terneo",
            model="Terneo BX"
        )

    @property
    def is_on(self) -> bool:
        """Return true if switch is on."""
        params_dict = self.coordinator.data.get("params_dict", {})
        value = params_dict.get(self._param_id)
        
        if value is None:
            return False
        
        try:
            return int(value) == 1
        except (ValueError, TypeError):
            return False

    async def async_turn_on(self, **kwargs):
        """Turn the switch on."""
        try:
            await self.api.set_parameter(self._param_id, 1, self._serial)
            
            import asyncio
            await asyncio.sleep(1)
            await self.coordinator.async_refresh()
            
        except CannotConnect:
            _LOGGER.error("Cannot connect to turn on %s", self._attr_name)
        except Exception as e:
            _LOGGER.error("Error turning on %s: %s", self._attr_name, e)

    async def async_turn_off(self, **kwargs):
        """Turn the switch off."""
        try:
            await self.api.set_parameter(self._param_id, 0, self._serial)
            
            import asyncio
            await asyncio.sleep(1)
            await self.coordinator.async_refresh()
            
        except CannotConnect:
            _LOGGER.error("Cannot connect to turn off %s", self._attr_name)
        except Exception as e:
            _LOGGER.error("Error turning off %s: %s", self._attr_name, e)


class TerneoChildLockSwitch(TerneoBaseSwitch):
    """Child lock switch."""

    def __init__(self, coordinator, api, host, serial):
        super().__init__(coordinator, api, host, serial, param_id=124, name="Child Lock", translation_key="night_brightness", icon="mdi:lock")
class TerneoNightBrightnessSwitch(TerneoBaseSwitch):
    """Night brightness mode switch."""

    def __init__(self, coordinator, api, host, serial):
        super().__init__(
            coordinator,
            api,
            host,
            serial,
            param_id=120,
            translation_key="night_brightness",
            icon="mdi:brightness-4"
        )
class TerneoPreheatSwitch(TerneoBaseSwitch):
    """Preheat control switch."""

    def __init__(self, coordinator, api, host, serial):
        super().__init__(
            coordinator,
            api,
            host,
            serial,
            param_id=121,
            translation_key="preheat",
            icon="mdi:fire"
        )

class TerneoWindowControlSwitch(TerneoBaseSwitch):
    """Window open control switch."""

    def __init__(self, coordinator, api, host, serial):
        super().__init__(
            coordinator,
            api,
            host,
            serial,
            param_id=122,
            translation_key="window_control",
            icon="mdi:window-open"
        )       