from __future__ import annotations
import logging
from datetime import datetime
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.restore_state import RestoreEntity
from .const import DOMAIN, ENERGY_UPDATE_INTERVAL_MAX, ENERGY_MIN_INCREMENT
from .api import TerneoApi, CannotConnect
from .coordinator import TerneoCoordinator

_LOGGER = logging.getLogger(__name__)

SENSOR_DEFS = [
    ('temp_air', 'Air Temperature', SensorDeviceClass.TEMPERATURE, '°C', SensorStateClass.MEASUREMENT),
    ('temp_floor', 'Floor Temperature', SensorDeviceClass.TEMPERATURE, '°C', SensorStateClass.MEASUREMENT),
    ('target_temp', 'Target Temperature', SensorDeviceClass.TEMPERATURE, '°C', SensorStateClass.MEASUREMENT),
    ('wifi_rssi', 'WiFi RSSI', SensorDeviceClass.SIGNAL_STRENGTH, 'dBm', SensorStateClass.MEASUREMENT),
]


async def async_setup_entry(hass, entry, async_add_entities):
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data['coordinator']
    api = data['api']
    host = entry.data.get('host')
    serial = coordinator.serial
    
    entities = []
    for key, title, dev_class, unit, state_class in SENSOR_DEFS:
        entities.append(TerneoCoordinatorSensor(coordinator, api, host, serial, key, title, dev_class, unit, state_class))

    # Специальный сенсор мощности с логикой
    entities.append(TerneoPowerSensor(coordinator, host, serial))
    
    # Счетчик энергии
    entities.append(TerneoEnergySensor(coordinator, host, serial))

    async_add_entities(entities, update_before_add=True)


class TerneoCoordinatorSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator: TerneoCoordinator, api: TerneoApi, host: str, serial: str, key: str, title: str, dev_class, unit: str | None, state_class):
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.api = api
        self._host = host
        self._serial = serial
        self._key = key
        self._attr_name = f"Terneo {host} {title}"
        self._attr_unique_id = f"terneo_{serial}_{key}"
        self._attr_device_class = dev_class
        self._attr_native_unit_of_measurement = unit
        self._attr_state_class = state_class

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
        return self.coordinator.data.get(self._key)


class TerneoPowerSensor(CoordinatorEntity, SensorEntity):
    """Сенсор мощности - зависит от состояния реле."""
    
    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "W"

    def __init__(self, coordinator: TerneoCoordinator, host: str, serial: str):
        super().__init__(coordinator)
        self._host = host
        self._serial = serial
        self._attr_name = f"Terneo {host} Power"
        self._attr_unique_id = f"terneo_{serial}_power_w"

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
        """Возвращает мощность в ваттах (0 если реле выключено)."""
        relay_state = self.coordinator.data.get('power', 0)
        
        if relay_state == 0:
            return 0
        
        power_w = self.coordinator.data.get('power_w', 0)
        return power_w

    @property
    def extra_state_attributes(self):
        """Дополнительные атрибуты для отладки."""
        relay_state = self.coordinator.data.get('power', 0)
        power_w = self.coordinator.data.get('power_w', 0)
        
        return {
            "heating_active": relay_state == 1,
            "relay_state": relay_state,
            "configured_power": power_w,
        }


class TerneoEnergySensor(CoordinatorEntity, RestoreEntity, SensorEntity):
    """Счетчик энергии в kWh с сохранением состояния."""
    
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = "kWh"

    def __init__(self, coordinator: TerneoCoordinator, host: str, serial: str):
        super().__init__(coordinator)
        self._host = host
        self._serial = serial
        self._attr_name = f"Terneo {host} Energy"
        self._attr_unique_id = f"terneo_{serial}_energy_kwh"
        self._total_energy = 0.0
        self._last_update = None
        self._last_power = 0

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._host)},  
            name=f"Terneo {self._host}",
            manufacturer="Terneo",
            model="Terneo BX"
        )

    async def async_added_to_hass(self):
        """Вызывается когда entity добавляется в HA."""
        await super().async_added_to_hass()
        
        # Восстанавливаем последнее сохраненное значение
        last_state = await self.async_get_last_state()
        if last_state is not None and last_state.state not in (None, "unknown", "unavailable"):
            try:
                self._total_energy = float(last_state.state)
                _LOGGER.info(f"Restored energy counter for {self._host}: {self._total_energy} kWh")
                
                # Восстанавливаем атрибуты
                if last_state.attributes:
                    last_update_str = last_state.attributes.get("last_update")
                    if last_update_str:
                        try:
                            self._last_update = datetime.fromisoformat(last_update_str)
                        except (ValueError, TypeError) as e:
                            _LOGGER.debug(f"Could not parse last_update: {e}")
                            self._last_update = None
                    
                    self._last_power = last_state.attributes.get("current_power", 0)
                    
            except (ValueError, TypeError) as e:
                _LOGGER.warning(f"Could not restore energy counter for {self._host}: {e}")
                self._total_energy = 0.0
        else:
            _LOGGER.info(f"No previous state found for energy counter {self._host}, starting from 0")

    @property
    def native_value(self):
        """Возвращает накопленную энергию в kWh."""
        # Получаем текущую мощность (зависит от реле)
        relay_state = self.coordinator.data.get('power', 0)
        power_w = self.coordinator.data.get('power_w', 0)
        
        # Реальная мощность = 0 если реле выключено
        current_power = power_w if relay_state == 1 else 0
        
        # Вычисляем приращение энергии
        now = datetime.now()
        if self._last_update is not None:
            time_delta_hours = (now - self._last_update).total_seconds() / 3600
            
            # Защита от аномально больших интервалов (больше 1 часа)
            # Это предотвращает скачки при перезапуске HA
            if time_delta_hours > ENERGY_UPDATE_INTERVAL_MAX / 3600:
                _LOGGER.debug(
                    f"Large time gap detected for {self._host}: {time_delta_hours:.2f}h. "
                    f"Skipping energy calculation to prevent anomaly."
                )
            elif time_delta_hours > 0:  # ← ДОБАВЛЕНО: защита от отрицательных значений
                # Используем среднюю мощность между двумя измерениями (метод трапеций)
                avg_power = (self._last_power + current_power) / 2
                energy_increment = (avg_power * time_delta_hours) / 1000  # Вт*ч → кВт*ч
                self._total_energy += energy_increment
                
                if energy_increment > ENERGY_MIN_INCREMENT:  
                    _LOGGER.debug(
                        f"Energy update for {self._host}: power={current_power}W, "
                        f"time_delta={time_delta_hours:.4f}h, "
                        f"increment={energy_increment:.6f}kWh, "
                        f"total={self._total_energy:.3f}kWh"
                    )
        
        self._last_update = now
        self._last_power = current_power
        
        return round(self._total_energy, 3)

    @property
    def extra_state_attributes(self):
        """Дополнительные атрибуты."""
        relay_state = self.coordinator.data.get('power', 0)
        power_w = self.coordinator.data.get('power_w', 0)
        current_power = power_w if relay_state == 1 else 0
        
        return {
            "last_update": self._last_update.isoformat() if self._last_update else None,
            "current_power": current_power,
            "heating_active": relay_state == 1,
        }