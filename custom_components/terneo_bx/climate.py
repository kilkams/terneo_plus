import logging
from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import UnitOfTemperature
from homeassistant.helpers.entity import DeviceInfo
from .const import DOMAIN
from .api import TerneoApi, CannotConnect

_LOGGER = logging.getLogger(__name__)

# Соответствие кодов устройства режимам HA
MODE_MAP = {
    "0": HVACMode.OFF,      # устройство выключено
    "3": HVACMode.HEAT,     # ручной режим (нагрев)
    "1": HVACMode.AUTO,     # авто (по расписанию)
}

REVERSE_MODE_MAP = {v: k for k, v in MODE_MAP.items()}


class TerneoClimate(ClimateEntity):
    """Основной климат-контроллер тернео."""

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE |
        ClimateEntityFeature.HVAC_MODE
    )
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT, HVACMode.AUTO]

    def __init__(self, api, host):
        self.api = api
        self._host = host

        self._attr_name = f"Terneo {host}"
        self._available = False

        self._current_temperature = None
        self._target_temperature = None
        self._hvac_mode = HVACMode.OFF
        self._relay_state = None

    @property
    def device_info(self):
        return DeviceInfo(
            identifiers={(DOMAIN, self._host)},
            name=f"Terneo {self._host}",
            manufacturer="Terneo",
        )

    @property
    def available(self):
        return self._available

    @property
    def current_temperature(self):
        return self._current_temperature

    @property
    def target_temperature(self):
        return self._target_temperature

    @property
    def hvac_mode(self):
        return self._hvac_mode

    async def async_set_temperature(self, **kwargs):
        """Установка уставки температуры (par.31)."""
        temp = kwargs.get("temperature")
        if temp is None:
            return

        try:
            await self.api.set_parameter(31, int(temp))
            self._target_temperature = temp
        except CannotConnect:
            _LOGGER.error("Cannot connect to set temperature")

        self.async_write_ha_state()

    async def async_set_hvac_mode(self, hvac_mode):
        """Установка режима работы."""
        mode_code = REVERSE_MODE_MAP.get(hvac_mode)
        if mode_code is None:
            _LOGGER.error("Unsupported HVAC mode %s", hvac_mode)
            return

        try:
            await self.api.set_mode(mode_code)
            self._hvac_mode = hvac_mode
        except CannotConnect:
            _LOGGER.error("Cannot connect to set HVAC mode")

        self.async_write_ha_state()

    async def async_update(self):
        """Обновление состояния из cmd=4 и cmd=1."""
        try:
            tele = await self.api.get_telemetry()

            # Температуры — t.0 = воздух, t.1 = пол
            if "t.0" in tele:
                self._current_temperature = round(int(tele["t.0"]) / 10, 1)

            # Реле
            self._relay_state = tele.get("f.10") == "1"

            # Режим m.1
            raw_mode = tele.get("m.1")
            self._hvac_mode = MODE_MAP.get(raw_mode, HVACMode.HEAT)

            # Параметры
            params = await self.api.get_parameters()
            for p_index, _type, p_value in params.get("par", []):
                if p_index == 31:
                    try:
                        self._target_temperature = int(p_value)
                    except ValueError:
                        pass

            self._available = True

        except CannotConnect:
            self._available = False

        except Exception as e:
            _LOGGER.error("Error updating climate: %s", e)
            self._available = False
