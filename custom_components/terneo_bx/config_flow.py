import asyncio
import socket
import voluptuous as vol
from homeassistant import config_entries
from .const import DOMAIN
from .options_flow import OptionsFlowHandler

class TerneoConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 2

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            mode = user_input.get("mode")
            if mode == "discover_broadcast":
                return await self.async_step_discover_broadcast()
            # ручной ввод
            host = user_input["host"]
            scan_interval = user_input.get("scan_interval", 20)
            return self.async_create_entry(
                title=f"Terneo {host}",
                data={"host": host, "scan_interval": scan_interval},
                options={"scan_interval": scan_interval},
            )

        schema = vol.Schema({
            vol.Required("mode", default="manual"): vol.In(["manual", "discover_broadcast"]),
            vol.Optional("host"): str,
            vol.Optional("scan_interval", default=20): int,
        })
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_discover_broadcast(self, user_input=None):
        errors = {}
        if user_input is not None:
            port = user_input.get("port", 9000)
            timeout = user_input.get("timeout", 5)
            scan_interval = user_input.get("scan_interval", 20)
            found = await self._async_broadcast_discover(port, timeout)
            if not found:
                errors["base"] = "not_found"
            else:
                host = found[0]
                return self.async_create_entry(
                    title=f"Terneo {host}",
                    data={"host": host, "scan_interval": scan_interval},
                    options={"scan_interval": scan_interval},
                )

        schema = vol.Schema({
            vol.Optional("port", default=9000): int,
            vol.Optional("timeout", default=5): int,
            vol.Optional("scan_interval", default=20): int,
        })
        return self.async_show_form(step_id="discover_broadcast", data_schema=schema, errors=errors)

    async def _async_broadcast_discover(self, port: int, timeout: float):
        found = set()
        loop = asyncio.get_running_loop()
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.bind(("", port))
        sock.setblocking(False)

        end = loop.time() + timeout
        while loop.time() < end:
            try:
                data, addr = await loop.sock_recvfrom(sock, 1024)
                found.add(addr[0])
            except Exception:
                await asyncio.sleep(0.1)

        sock.close()
        return list(found)

    async def async_get_options_flow(self, entry):
        return OptionsFlowHandler(entry)
