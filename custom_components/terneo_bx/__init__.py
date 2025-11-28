import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN, DEFAULT_SCAN_INTERVAL
from .api import TerneoApi
from .coordinator import TerneoCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Terneo BX component."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Terneo BX from config entry."""

    host = entry.data["host"]
    serial = entry.data.get("serial")  
    scan_interval = entry.options.get(
        "scan_interval",
        entry.data.get("scan_interval", DEFAULT_SCAN_INTERVAL)
    )

    api = TerneoApi(host, sn=serial)

    # Если serial отсутствует - получаем его из телеметрии
    if not serial:
        _LOGGER.warning("Serial number not found in config, fetching from device...")
        try:
            telemetry = await api.get_telemetry()
            serial = telemetry.get("sn")
            if serial:
                _LOGGER.info("Got serial number from device: %s", serial)
                # Обновляем конфигурацию
                hass.config_entries.async_update_entry(
                    entry,
                    data={**entry.data, "serial": serial}
                )
                # Обновляем API с полученным serial
                api.sn = serial
            else:
                _LOGGER.error("Could not get serial number from device")
        except Exception as e:
            _LOGGER.error("Failed to fetch serial from device: %s", e)

    coordinator = TerneoCoordinator(
        hass=hass,
        api=api,
        update_interval=timedelta(seconds=scan_interval),
        serial=serial,
        host=host, 
    )

    # первый fetch данных
    await coordinator.async_config_entry_first_refresh()

    # сохраняем API и coordinator
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "api": api,
        "coordinator": coordinator,
    }

    # запускаем платформы
    await hass.config_entries.async_forward_entry_setups(
        entry,
        ["climate", "sensor", "binary_sensor", "calendar"]
    )

    # Регистрируем сервис сброса счетчика энергии (только один раз)
    if not hass.services.has_service(DOMAIN, "reset_energy"):
        async def reset_energy(call):
            """Сброс счетчика энергии."""
            entity_id = call.data.get("entity_id")
            
            if not entity_id:
                _LOGGER.error("entity_id is required for reset_energy service")
                return
            
            # Получаем entity из entity registry
            ent_reg = er.async_get(hass)
            entity_entry = ent_reg.async_get(entity_id)
            
            if not entity_entry:
                _LOGGER.error(f"Entity {entity_id} not found")
                return
            
            # Получаем объект entity из hass.states
            entity = hass.data["entity_components"]["sensor"].get_entity(entity_id)
            
            if entity and hasattr(entity, '_total_energy'):
                _LOGGER.info(f"Resetting energy counter for {entity_id}")
                entity._total_energy = 0.0
                entity._last_update = None
                entity._last_power = 0
                entity.async_write_ha_state()
            else:
                _LOGGER.error(f"Entity {entity_id} is not an energy sensor or doesn't support reset")
        
        hass.services.async_register(DOMAIN, "reset_energy", reset_energy)
        _LOGGER.info("Registered reset_energy service")

    _LOGGER.info("Terneo BX setup completed for %s (SN: %s)", host, serial)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload entry."""

    unload_ok = await hass.config_entries.async_unload_platforms(
        entry,
        ["climate", "sensor", "binary_sensor", "calendar"]
    )

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        
        # Удаляем сервис, если это последняя интеграция Terneo
        if not hass.data[DOMAIN]:
            hass.services.async_remove(DOMAIN, "reset_energy")
            _LOGGER.info("Removed reset_energy service")

    return unload_ok