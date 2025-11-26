import voluptuous as vol
from homeassistant import config_entries

from .const import DOMAIN, DEFAULT_SCAN_INTERVAL


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Manage integration options."""

    def __init__(self, entry):
        self.entry = entry

    async def async_step_init(self, user_input=None):
        errors = {}

        if user_input is not None:
            scan_interval = user_input.get("scan_interval", DEFAULT_SCAN_INTERVAL)

            return self.async_create_entry(
                title="",
                data={"scan_interval": scan_interval},
            )

        schema = vol.Schema({
            vol.Optional(
                "scan_interval",
                default=self.entry.options.get(
                    "scan_interval",
                    self.entry.data.get("scan_interval", DEFAULT_SCAN_INTERVAL)
                )
            ): int
        })

        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)
