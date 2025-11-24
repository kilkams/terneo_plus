import aiohttp
import async_timeout

class TerneoAPI:
    def __init__(self, host):
        self._url = f"http://{host}/api.cgi"
        self._session = None

    async def _ensure_session(self):
        if self._session is None:
            self._session = aiohttp.ClientSession()

    async def close(self):
        if self._session is not None:
            await self._session.close()
            self._session = None

    async def _request(self, payload):
        await self._ensure_session()
        try:
            async with async_timeout.timeout(6):
                async with self._session.post(self._url, json=payload, headers={"Content-Type": "application/json"}) as resp:
                    if resp.status == 200:
                        return await resp.json()
        except Exception:
            return None

    async def get_raw(self):
        return await self._request({"cmd": 1, "par": []})

    async def get_telemetry(self):
        return await self._request({"cmd": 4})

    async def set_parameter(self, sn: str, param_id: int, value):
        payload = {
            "cmd": 2,
            "sn": sn,
            "par": [[param_id, value]]
        }
        return await self._request(payload)

    async def set_temperature(self, temperature: float, sn: str, param_id: int = 31):
        return await self.set_parameter(sn, param_id, int(temperature))

    async def get_schedule(self, sn: str):
        payload = {"cmd": 2, "sn": sn}
        return await self._request(payload)

    async def set_schedule(self, sn: str, schedule: dict):
        payload = {"cmd": 2, "sn": sn, "tt": schedule}
        return await self._request(payload)

    @staticmethod
    async def discover_subnet(hass, subnet_cidr: str, timeout_per_host: float = 0.8):
        import ipaddress
        import asyncio
        import async_timeout
        import aiohttp

        hosts = []
        try:
            net = ipaddress.ip_network(subnet_cidr, strict=False)
        except Exception:
            return hosts

        sem = asyncio.Semaphore(200)

        async def check_ip(ip):
            url = f"http://{ip}/api.cgi"
            try:
                async with sem:
                    async with aiohttp.ClientSession() as session:
                        async with async_timeout.timeout(timeout_per_host):
                            async with session.post(url, json={"cmd":1, "par": []}, headers={"Content-Type":"application/json"}) as resp:
                                if resp.status == 200:
                                    data = await resp.json()
                                    if data and isinstance(data, dict) and "par" in data:
                                        hosts.append(str(ip))
            except Exception:
                return

        tasks = [check_ip(str(ip)) for ip in net.hosts()]
        await asyncio.gather(*tasks)
        return hosts

    @staticmethod
    async def discover_broadcast(port: int = 9000, timeout: float = 5.0):
        import asyncio
        import socket

        found = set()
        loop = asyncio.get_running_loop()
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.bind(("", port))
        sock.setblocking(False)

        end = loop.time() + timeout
        while loop.time() < end:
            try:
                data, addr = await loop.sock_recvfrom(sock, 2048)
                found.add(addr[0])
            except Exception:
                await asyncio.sleep(0.1)

        sock.close()
        return list(found)
