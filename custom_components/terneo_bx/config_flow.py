import asyncio, socket, voluptuous as vol
from homeassistant import config_entries
from .const import DOMAIN, DEFAULT_SCAN_INTERVAL
from .api import TerneoApi

class TerneoConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 2

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            mode = user_input.get('mode')
            if mode == 'discover_broadcast':
                return await self.async_step_discover_broadcast()
            host = user_input.get('host')
            scan_interval = user_input.get('scan_interval', DEFAULT_SCAN_INTERVAL)
            if not host:
                errors['host'] = 'host_required'
            else:
                # Проверяем подключение и получаем serial
                result = await self._async_test_connection(host)
                if not result:
                    errors['base'] = 'cannot_connect'
                else:
                    serial = result.get('serial')
                    return self.async_create_entry(
                        title=f'Terneo {host}',
                        data={
                            'host': host,
                            'serial': serial,  # ← Сохраняем serial
                            'scan_interval': scan_interval
                        },
                        options={'scan_interval': scan_interval}
                    )
        
        schema = vol.Schema({
            vol.Required('mode', default='manual'): vol.In(['manual', 'discover_broadcast']),
            vol.Optional('host'): str,
            vol.Optional('scan_interval', default=DEFAULT_SCAN_INTERVAL): int
        })
        return self.async_show_form(step_id='user', data_schema=schema, errors=errors)

    async def async_step_discover_broadcast(self, user_input=None):
        errors = {}
        if user_input is not None:
            port = user_input.get('port', 9000)
            timeout = user_input.get('timeout', 4)
            scan_interval = user_input.get('scan_interval', DEFAULT_SCAN_INTERVAL)
            found = await self._async_discover(port, timeout)
            if not found:
                errors['base'] = 'not_found'
            else:
                host = found[0]
                # Проверяем подключение и получаем serial
                result = await self._async_test_connection(host)
                if not result:
                    errors['base'] = 'cannot_connect'
                else:
                    serial = result.get('serial')
                    return self.async_create_entry(
                        title=f'Terneo {host}',
                        data={
                            'host': host,
                            'serial': serial,  # ← Сохраняем serial
                            'scan_interval': scan_interval
                        },
                        options={'scan_interval': scan_interval}
                    )
        
        schema = vol.Schema({
            vol.Optional('port', default=9000): int,
            vol.Optional('timeout', default=4): int,
            vol.Optional('scan_interval', default=DEFAULT_SCAN_INTERVAL): int
        })
        return self.async_show_form(step_id='discover_broadcast', data_schema=schema, errors=errors)

    async def _async_test_connection(self, host: str) -> dict | None:
        """Проверяет подключение и возвращает данные устройства."""
        api = TerneoApi(host)
        try:
            tele = await api.get_telemetry()
            if tele is not None:
                serial = tele.get("sn")
                return {
                    "success": True,
                    "serial": serial
                }
            return None
        except Exception:
            return None

    async def _async_discover(self, port: int, timeout: int):
        loop = asyncio.get_running_loop()
        found = set()
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        try:
            sock.bind(('', port))
        except Exception:
            return []
        sock.setblocking(False)
        end = loop.time() + timeout
        while loop.time() < end:
            try:
                data, addr = await loop.sock_recvfrom(sock, 1024)
                found.add(addr[0])
            except Exception:
                await asyncio.sleep(0.05)
        sock.close()
        return list(found)

    @staticmethod
    def async_get_options_flow(entry):
        from .options_flow import OptionsFlowHandler
        return OptionsFlowHandler(entry)