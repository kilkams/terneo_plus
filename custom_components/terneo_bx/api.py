import logging, aiohttp, async_timeout
from typing import Any, Dict

from .const import API_ENDPOINT, CMD_TELEMETRY, CMD_PARAMS, CMD_SET_PARAM

_LOGGER = logging.getLogger(__name__)

class CannotConnect(Exception):
    pass

class TerneoApi:
    def __init__(self, host: str, sn: str | None = None):
        self.host = host.rstrip("/")
        self.sn = sn

    async def _post(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        url = f"http://{self.host}{API_ENDPOINT}"
        _LOGGER.debug("POST %s -> %s", url, payload)
        try:
            async with async_timeout.timeout(10):
                async with aiohttp.ClientSession() as session:
                    async with session.post(url, json=payload) as resp:
                        raw = await resp.text()
                        if resp.status != 200:
                            raise CannotConnect(f"HTTP {resp.status}: {raw}")
                        try:
                            return await resp.json()
                        except Exception as e:
                            _LOGGER.debug("Invalid JSON response: %s", raw)
                            raise CannotConnect(f"Invalid JSON: {e}")
        except Exception as e:
            raise CannotConnect(f"API request failed: {e}")

    # READ
    async def get_params(self) -> Dict[str, Any] | None:
        return await self._post({"cmd": CMD_PARAMS})

    async def get_schedule(self) -> Dict[str, Any] | None:
        return await self._post({"cmd": 2})

    async def get_time(self) -> Dict[str, Any] | None:
        return await self._post({"cmd": 3})

    async def get_telemetry(self) -> Dict[str, Any] | None:
        return await self._post({"cmd": CMD_TELEMETRY})

    # WRITE: set parameter (must include sn when writing)
    async def set_parameter(self, par_index: int, value: Any, sn: str | None = None):
        body = {"cmd": CMD_SET_PARAM, "par": [[par_index, value]]}
        if sn or self.sn:
            body["sn"] = sn or self.sn
        return await self._post(body)

    async def set_schedule(self, day: int, periods: list, sn: str | None = None):
        """Set schedule for single day. periods = [[minute, temp], ...]"""
        body = {"cmd": 2, "tt": {str(day): periods}}
        if sn or self.sn:
            body["sn"] = sn or self.sn
        return await self._post(body)

    async def set_parameters(self, params: dict, sn: str | None = None):
        """Legacy bulk params write (uses cmd=3 in some devices)"""
        par_list = []
        for k, v in params.items():
            try:
                idx = int(k)
            except:
                idx = k
            par_list.append([idx, v])
        body = {"cmd": 3, "par": par_list}
        if sn or self.sn:
            body["sn"] = sn or self.sn
        return await self._post(body)

    # HELPERS
    @staticmethod
    def extract_param(params: dict, pid: int):
        arr = params.get("par", []) if isinstance(params, dict) else []
        for item in arr:
            try:
                if item[0] == pid:
                    return item[2]
            except Exception:
                continue
        return None

    @staticmethod
    def extract_int(obj: dict, field: str):
        try:
            if field in obj:
                return int(obj[field])
        except Exception:
            return None
        return None
