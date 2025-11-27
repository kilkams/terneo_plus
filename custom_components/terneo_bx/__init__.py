import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN, DEFAULT_SCAN_INTERVAL
from .api import TerneoApi
from .coordinator import TerneoCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Terneo BX from config entry."""

    host = entry.data["host"]
    serial = entry.data.get("serial")  
    scan_interval = entry.options.get(
        "scan_interval",
        entry.data.get("scan_interval", DEFAULT_SCAN_INTERVAL)
    )

    api = TerneoApi(host, sn=serial)

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

    _LOGGER.info("Terneo BX setup completed for %s", host)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload entry."""

    unload_ok = await hass.config_entries.async_unload_platforms(
        entry,
        ["climate", "sensor", "binary_sensor", "calendar"]
    )

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)

    return unload_ok