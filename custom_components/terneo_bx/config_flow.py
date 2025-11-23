
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from .const import DOMAIN

class TerneoFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION=1

    async def async_step_user(self, user_input=None):
        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema({
                    vol.Required("host"): str,
                    vol.Required("serial"): str,
                })
            )
        return self.async_create_entry(title=f"Terneo {user_input['host']}", data=user_input)
