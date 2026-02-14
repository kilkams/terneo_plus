import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN, DEFAULT_SCAN_INTERVAL, DEFAULT_DELAY_MULTIPLIER
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
    
    # Получаем scan_interval из options (если есть) или из data
    scan_interval = entry.options.get(
        "scan_interval",
        entry.data.get("scan_interval", DEFAULT_SCAN_INTERVAL)
    )
    
    # Получаем delay_multiplier из options (если есть) или из data
    delay_multiplier = entry.options.get(
        "delay_multiplier",
        entry.data.get("delay_multiplier", DEFAULT_DELAY_MULTIPLIER)
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
        delay_multiplier=delay_multiplier,  # Передаем параметр
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
        ["climate", "sensor", "binary_sensor", "switch", "number", "calendar"]
    )

    # Регистрируем сервисы (только один раз)
    await _register_services(hass)

    # Подписываемся на изменения options
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    _LOGGER.info("Terneo BX setup completed for %s (SN: %s), delay_multiplier: %.2f", host, serial, delay_multiplier)
    return True


async def _register_services(hass: HomeAssistant):
    """Register integration services."""
    
    async def _find_device_by_entity(entity_id: str):
        """Найти устройство по entity_id."""
        _LOGGER.debug(f"Searching for device with entity_id: {entity_id}")
        
        for entry_id, entry_data in hass.data[DOMAIN].items():
            coordinator = entry_data.get("coordinator")
            if not coordinator:
                continue
            
            # Проверяем по serial или host в entity_id
            # entity_id может быть вида: climate.terneo_192_168_15_241
            # или sensor.terneo_SERIAL_power_w
            if (coordinator.serial and coordinator.serial.lower() in entity_id.lower()) or \
               (coordinator.host and coordinator.host.replace(".", "_") in entity_id):
                _LOGGER.debug(f"Found device: host={coordinator.host}, serial={coordinator.serial}")
                return coordinator.host
        
        _LOGGER.error(f"Could not find device for entity_id: {entity_id}")
        return None
    
    async def _send_test_command(entity_id: str, cmd: str) -> bool:
        """Отправить команду на test.cgi endpoint."""
        if not entity_id:
            _LOGGER.error(f"entity_id is required for {cmd} service")
            return False
        
        host = await _find_device_by_entity(entity_id)
        if not host:
            return False
        
        try:
            _LOGGER.info(f"Sending '{cmd}' command to {host}")
            url = f"http://{host}/test.cgi"
            
            import aiohttp
            import async_timeout
            
            async with async_timeout.timeout(10):
                async with aiohttp.ClientSession() as session:
                    async with session.post(url, json={"cmd": cmd}) as resp:
                        result = await resp.text()
                        _LOGGER.debug(f"Response from {host}: {result}")
                        
                        if resp.status == 200:
                            _LOGGER.info(f"Command '{cmd}' sent successfully to {host}: {result}")
                            return True
                        else:
                            _LOGGER.error(f"Command '{cmd}' failed: HTTP {resp.status}, response: {result}")
                            return False
                            
        except Exception as e:
            _LOGGER.error(f"Error sending '{cmd}' command to {host}: {e}", exc_info=True)
            return False
    
    # Сервис reset_energy
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
            
            # Получаем объект entity
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
    
    # Сервис blink
    if not hass.services.has_service(DOMAIN, "blink"):
        async def blink_device(call):
            """Заставить устройство моргнуть индикатором."""
            entity_id = call.data.get("entity_id")
            await _send_test_command(entity_id, "blink")
        
        hass.services.async_register(DOMAIN, "blink", blink_device)
        _LOGGER.info("Registered blink service")
    
    # Сервис restart
    if not hass.services.has_service(DOMAIN, "restart"):
        async def restart_device(call):
            """Перезагрузить устройство."""
            entity_id = call.data.get("entity_id")
            await _send_test_command(entity_id, "restart")
        
        hass.services.async_register(DOMAIN, "restart", restart_device)
        _LOGGER.info("Registered restart service")

    if not hass.services.has_service(DOMAIN, "reset_api_errors"):
        async def reset_api_errors(call):
            """Сброс счетчика ошибок API."""
            entity_id = call.data.get("entity_id")
            
            if not entity_id:
                _LOGGER.error("entity_id is required for reset_api_errors service")
                return
            
            host = await _find_device_by_entity(entity_id)
            if not host:
                return
            
            # Находим API объект
            for entry_id, entry_data in hass.data[DOMAIN].items():
                coordinator = entry_data.get("coordinator")
                if coordinator and coordinator.host == host:
                    api = entry_data.get("api")
                    if api:
                        api.reset_error_count()
                        _LOGGER.info(f"API error counter reset for {host}")
                    break
        
        hass.services.async_register(DOMAIN, "reset_api_errors", reset_api_errors)
        _LOGGER.info("Registered reset_api_errors service")    


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload entry."""

    unload_ok = await hass.config_entries.async_unload_platforms(
        entry,
        ["climate", "sensor", "binary_sensor", "switch", "number", "calendar"]
    )

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        
        # Удаляем сервисы, если это последняя интеграция Terneo
        if not hass.data[DOMAIN]:
            hass.services.async_remove(DOMAIN, "reset_energy")
            hass.services.async_remove(DOMAIN, "blink")
            hass.services.async_remove(DOMAIN, "restart")
            hass.services.async_remove(DOMAIN, "reset_api_errors")
            _LOGGER.info("Removed all Terneo services")

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry when options change."""
    await hass.config_entries.async_reload(entry.entry_id)