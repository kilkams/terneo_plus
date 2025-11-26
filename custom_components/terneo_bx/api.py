import logging
import aiohttp
import async_timeout

from .const import (
    API_ENDPOINT,
    CMD_TELEMETRY,
    CMD_PARAMS,
    CMD_SET_PARAM
)

class CannotConnect(Exception):
    """Ошибка подключения к термостату."""
    pass

_LOGGER = logging.getLogger(__name__)


class TerneoApi:
    """Low-level API client for Terneo thermostats."""

    def __init__(self, host: str):
        self.host = host.rstrip("/")

    async def _post(self, payload: dict) -> dict | None:
        """Perform POST to http://host/api.cgi"""
        url = f"http://{self.host}{API_ENDPOINT}"
        _LOGGER.debug("Terneo POST %s -> %s", url, payload)

        try:
            async with async_timeout.timeout(10):
                async with aiohttp.ClientSession() as session:
                    async with session.post(url, json=payload) as resp:
                        if resp.status != 200:
                            raise CannotConnect(f"HTTP {resp.status}")

                        return await resp.json()

        except Exception as e:
            raise CannotConnect(f"API request failed: {e}")

    # ---------------------------------------------------------------------
    # TELEMETRY — cmd=4
    # ---------------------------------------------------------------------
    async def get_telemetry(self):
        """Get telemetry (cmd=4)."""
        return await self._post({"cmd": CMD_TELEMETRY})


    async def get_parameters(self):
        """Получение параметров cmd=1"""
        return await self._post({"cmd": 1})

    # ---------------------------------------------------------------------
    # PARAMS — cmd=1
    # ---------------------------------------------------------------------
    async def get_params(self):
        """Get full parameters array (cmd=1)."""
        return await self._post({"cmd": CMD_PARAMS})

    # ---------------------------------------------------------------------
    # SET PARAM — cmd=2
    # ---------------------------------------------------------------------
    async def set_parameter(self, par_index: int, value: int):
        payload = {"cmd": 2, "par": [[par_index, value]]}
        return await self._post(payload)

    # ---------------------------------------------------------------------
    # HELPERS
    # ---------------------------------------------------------------------
    @staticmethod
    def extract_param(params: dict, pid: int):
        """Extract parameter value by ID from cmd=1 result."""
        arr = params.get("par", [])
        for item in arr:
            if item[0] == pid:
                return item[2]
        return None

    @staticmethod
    def extract_int(obj: dict, field: str) -> int | None:
        """Extract int value from telemetry fields like t.0, o.0 etc."""
        if field not in obj:
            return None
        try:
            return int(obj[field])
        except Exception:
            return None

    @staticmethod
    def extract_float(obj: dict, field: str) -> float | None:
        if field not in obj:
            return None
        try:
            return float(obj[field])
        except Exception:
            return None

    async def set_mode(self, mode_code: int):
        """Установка режима через параметр 17."""
        payload = {"cmd": CMD_SET_PARAM, "par": [[17, mode_code]]}
        return await self._post(payload)