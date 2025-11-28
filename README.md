# Terneo BX Integration for Home Assistant
[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)

Home Assistant integration for Terneo BX smart thermostats with local API support.

## Features

### Climate Control
- **HVAC Modes**: Off, Heat (Manual), Auto (Schedule)
- **Temperature Control**: Set target temperature with automatic mode switching
- **Current Temperature**: Real-time air and floor temperature monitoring
- **Smart Mode Switching**: Automatically switches to manual mode when setting temperature

### Sensors
- **Air Temperature**: Current air temperature (°C)
- **Floor Temperature**: Current floor temperature (°C)
- **Target Temperature**: Current target temperature setpoint
- **Power**: Real-time power consumption (W) - shows 0 when heating is off
- **Energy**: Total energy consumption counter (kWh) with reset service
- **WiFi RSSI**: Signal strength indicator (dBm)

For the energy sensor to work, you need to correctly specify the power of the connected load.
You need to measure the voltage and current. Use the formula U*I.

### Binary Sensors
- **Heating Active**: Shows when the heating relay is on/off

### Calendar
- **Weekly Schedule**: Displays heating schedule in Home Assistant calendar
- **Current Event**: Shows active temperature setpoint from schedule
- **Temperature Events**: Each schedule period appears as calendar event with target temperature

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant
2. Go to "Integrations"
3. Click the three dots menu → "Custom repositories"
4. Add repository URL: `https://github.com/kilkams/terneo_plus`
5. Category: `Integration`
6. Click "Add"
7. Find "Terneo BX" in HACS and click "Download"
8. Restart Home Assistant

### Manual Installation

1. Download the latest release from [GitHub](https://github.com/kilkams/terneo_plus/releases)
2. Copy the `custom_components/terneo_bx` folder to your Home Assistant `custom_components` directory
3. Restart Home Assistant

## Configuration

### Prerequisites

Your Terneo BX device must have:
- Firmware version 2.3 or newer
- Local network access enabled (see [Terneo API Documentation](https://github.com/MxmLtv/terneo-api))
- Static IP address or DHCP reservation recommended

### Setup via UI

1. Go to **Settings** → **Devices & Services**
2. Click **"+ Add Integration"**
3. Search for **"Terneo BX"**
4. Choose setup method:
   - **Manual**: Enter device IP address manually
   - **Auto-discovery**: Automatically find devices on your network (UDP broadcast on port 9000)
5. Configure scan interval (default: 30 seconds)
6. Click **Submit**

The integration will automatically detect the device serial number and configure all entities.

## Entities

After setup, the following entities will be created:

### Climate Entity
- `climate.terneo_[IP]` - Main thermostat control

### Sensors
- `sensor.terneo_[IP]_air_temperature` - Air temperature
- `sensor.terneo_[IP]_floor_temperature` - Floor temperature
- `sensor.terneo_[IP]_target_temperature` - Target temperature setpoint
- `sensor.terneo_[IP]_power` - Current power consumption
- `sensor.terneo_[IP]_energy` - Total energy consumption
- `sensor.terneo_[IP]_wifi_rssi` - WiFi signal strength

### Binary Sensors
- `binary_sensor.terneo_[IP]_heating_active` - Heating relay state

### Calendar
- `calendar.terneo_[IP]_schedule` - Weekly heating schedule

## Services

### Reset Energy Counter

Reset the energy consumption counter to zero.
```yaml
service: terneo_bx.reset_energy
data:
  entity_id: sensor.terneo_192_168_1_100_energy

***Thanks to ChatGPT and Claude.io for their help in developing the integration.