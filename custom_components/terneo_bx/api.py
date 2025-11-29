import logging, aiohttp, async_timeout, asyncio
from typing import Any, Dict
from datetime import datetime
from .const import API_ENDPOINT, CMD_TELEMETRY, CMD_PARAMS, CMD_SET_PARAM, PARAM_TYPES

_LOGGER = logging.getLogger(__name__)

class CannotConnect(Exception):
    pass

class TerneoApi:
    def __init__(self, host: str, sn: str | None = None):
        self.host = host.rstrip("/")
        self.sn = sn
        self.error_count = 0  
        self.last_error = None  
        self.last_success = None  
        _LOGGER.info("TerneoApi initialized with host=%s, sn=%s", host, sn)
    async def _post(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        url = f"http://{self.host}{API_ENDPOINT}"
        _LOGGER.debug("POST %s -> %s", url, payload)
        try:
            async with async_timeout.timeout(10):
                async with aiohttp.ClientSession() as session:
                    async with session.post(url, json=payload) as resp:
                        raw = await resp.text()
                        if resp.status != 200:
                            self.error_count += 1  
                            self.last_error = f"HTTP {resp.status}"                           
                            raise CannotConnect(f"HTTP {resp.status}: {raw}")
                        try:
                            data = await resp.json()
                            self.last_success = datetime.now()                                                        
                            return data
                        except Exception as e:
                            self.error_count += 1  
                            self.last_error = f"Invalid JSON: {e}"                             
                            _LOGGER.debug("Invalid JSON response: %s", raw)
                            raise CannotConnect(f"Invalid JSON: {e}")
        except asyncio.TimeoutError:
            self.error_count += 1 
            self.last_error = "Timeout"  
            raise CannotConnect("Request timeout")                        
        except Exception as e:
            self.error_count += 1 
            self.last_error = str(e)            
            raise CannotConnect(f"API request failed: {e}")

    def reset_error_count(self):
        """Сброс счетчика ошибок."""
        self.error_count = 0
        self.last_error = None
        _LOGGER.info(f"Error counter reset for {self.host}")

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
    async def set_parameter(self, param_id: int, value: Any, sn: str | None = None):
        param_type = PARAM_TYPES.get(param_id)
        
        if param_type is None:
            _LOGGER.warning(f"Unknown parameter type for ID={param_id}, using default type 2 (uint8)")
            param_type = 2
        
        body = {"cmd": CMD_SET_PARAM, "par": [[param_id, param_type, str(value)]]}
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
