import voluptuous as vol
from homeassistant import config_entries
from .const import DEFAULT_SCAN_INTERVAL

class OptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, entry):
        self.entry = entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title='', data=user_input)
        schema = vol.Schema({vol.Optional('scan_interval', default=self.entry.options.get('scan_interval', self.entry.data.get('scan_interval', DEFAULT_SCAN_INTERVAL))): int})
        return self.async_show_form(step_id='init', data_schema=schema)
