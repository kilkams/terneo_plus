import voluptuous as vol
from homeassistant import config_entries
from .const import DEFAULT_SCAN_INTERVAL, DEFAULT_DELAY_MULTIPLIER


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for Terneo BX."""

    def __init__(self, entry: config_entries.ConfigEntry):
        self.entry = entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
 
        # Получаем текущие значения из options или data
        current_scan_interval = self.entry.options.get(
            'scan_interval',
            self.entry.data.get('scan_interval', DEFAULT_SCAN_INTERVAL)
        )
        
        current_delay_multiplier = self.entry.options.get(
            'delay_multiplier',
            self.entry.data.get('delay_multiplier', DEFAULT_DELAY_MULTIPLIER)
        )

        schema = vol.Schema({
            vol.Optional(
                'scan_interval',
                default=current_scan_interval
            ): vol.All(vol.Coerce(int), vol.Range(min=5, max=300)),
            
            vol.Optional(
                'delay_multiplier',
                default=current_delay_multiplier
            ): vol.All(vol.Coerce(float), vol.Range(min=0.5, max=5.0)),
        })

        return self.async_show_form(step_id="init", data_schema=schema)