import asyncio
import json
import random
import ssl
import time
import uuid
import aiohttp
import aiofiles
from colorama import Fore, Style, init
from loguru import logger
from websockets_proxy import Proxy, proxy_connect

init(autoreset=True)
CONFIG_FILE = "config.json"
PING_INTERVAL = 30  
DIRECTOR_SERVER = "https://director.getgrass.io"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
}
ERROR_PATTERNS = [
    "Host unreachable",
    "[SSL: WRONG_VERSION_NUMBER]",
    "invalid length of packed IP address string",
    "Empty connect reply",
    "Device creation limit exceeded",
    "sent 1011 (internal error) keepalive ping timeout"
]

async def get_ws_endpoints(user_id: str):
    url = f"{DIRECTOR_SERVER}/checkin"
    headers = {"Content-Type": "application/json"}
    data = {
        "browserId": user_id,
        "userId": user_id,
        "version": "4.29.0",
        "extensionId": "lkbnfiajjmbhnfledhphioinpickokdi",
        "userAgent": HEADERS["User-Agent"],
        "deviceType": "extension"
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=data, headers=headers) as response:
            if response.status == 201:
                try:
                    result = await response.json(content_type=None)
                except Exception as e:
                    logger.error(f"Error decoding JSON: {e}")
                    text = await response.text()
                    result = json.loads(text)
                destinations = result.get("destinations", [])
                token = result.get("token", "")
                destinations = [f"wss://{dest}" for dest in destinations]
                return destinations, token
            else:
                logger.error(f"Failed to check in: Status {response.status}")
                return [], ""

class WebSocketClient:
    def __init__(self, socks5_proxy: str, user_id: str):
        self.proxy = socks5_proxy
        self.user_id = user_id
        self.device_id = str(uuid.uuid3(uuid.NAMESPACE_DNS, socks5_proxy))
        self.uri = None

    async def connect(self) -> bool:
        logger.info(f"🖥️ Device ID: {self.device_id}")
        while True:
            try:
                endpoints, token = await get_ws_endpoints(self.user_id)
                if not endpoints or not token:
                    logger.error("No valid WebSocket endpoints or token received")
                    return False
                self.uri = f"{endpoints[0]}?token={token}"
                logger.info(f"Connecting to WebSocket URI: {self.uri}")

                await asyncio.sleep(0.1)
                ssl_context = ssl.create_default_context()
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE

                async with proxy_connect(
                    self.uri,
                    proxy=Proxy.from_url(self.proxy),
                    ssl=ssl_context,
                    extra_headers=HEADERS
                ) as websocket:
                    ping_task = asyncio.create_task(self._send_ping(websocket))
                    try:
                        await self._handle_messages(websocket)
                    finally:
                        ping_task.cancel()
                        try:
                            await ping_task
                        except asyncio.CancelledError:
                            pass
            except Exception as e:
                logger.error(f"🚫 Error with proxy {self.proxy}: {str(e)}")
                if any(pattern in str(e) for pattern in ERROR_PATTERNS):
                    logger.info(f"❌ Removing error proxy from list: {self.proxy}")
                    await self._remove_proxy_from_list()
                    return False
                await asyncio.sleep(5)

    async def _send_ping(self, websocket) -> None:
        while True:
            try:
                message = {
                    "id": str(uuid.uuid4()),
                    "version": "1.0.0",
                    "action": "PING",
                    "data": {}
                }
                await websocket.send(json.dumps(message))
                await asyncio.sleep(PING_INTERVAL)
            except Exception as e:
                logger.error(f"🚫 Error sending ping: {str(e)}")
                break

    async def _handle_messages(self, websocket) -> None:
        handlers = {
            "AUTH": self._handle_auth,
            "PONG": self._handle_pong
        }
        while True:
            response = await websocket.recv()
            message = json.loads(response)
            logger.info(f"📥 Received message: {message}")
            handler = handlers.get(message.get("action"))
            if handler:
                await handler(websocket, message)

    async def _handle_auth(self, websocket, message) -> None:
        auth_response = {
            "id": message["id"],
            "origin_action": "AUTH",
            "result": {
                "browser_id": self.device_id,
                "user_id": self.user_id,
                "user_agent": HEADERS["User-Agent"],
                "timestamp": int(time.time()),
                "device_type": "extension", 
                "version": "4.29.0",
            }
        }
        await websocket.send(json.dumps(auth_response))

    async def _handle_pong(self, websocket, message) -> None:
        pong_response = {
            "id": message["id"],
            "origin_action": "PONG"
        }
        await websocket.send(json.dumps(pong_response))

    async def _remove_proxy_from_list(self) -> None:
        try:
            async with aiofiles.open("proxy.txt", "r") as file:
                lines = await file.readlines()
            async with aiofiles.open("proxy.txt", "w") as file:
                await file.writelines(line for line in lines if line.strip() != self.proxy)
        except Exception as e:
            logger.error(f"🚫 Error removing proxy from file: {str(e)}")

class ProxyManager:
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.active_proxies = set()
        self.all_proxies = set()

    async def load_proxies(self) -> None:
        try:
            async with aiofiles.open("proxy.txt", "r") as file:
                content = await file.read()
            self.all_proxies = set(line.strip() for line in content.splitlines() if line.strip())
        except Exception as e:
            logger.error(f"❌ Error loading proxies: {str(e)}")

    async def start(self, max_proxies: int) -> None:
        await self.load_proxies()
        if not self.all_proxies:
            logger.error("❌ No proxies found in proxy.txt")
            return
        self.active_proxies = set(random.sample(list(self.all_proxies), min(len(self.all_proxies), max_proxies)))
        tasks = {asyncio.create_task(self._run_client(proxy)): proxy for proxy in self.active_proxies}

        while True:
            done, pending = await asyncio.wait(tasks.keys(), return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                proxy = tasks.pop(task)
                if task.result() is False:
                    self.active_proxies.remove(proxy)
                    await self.load_proxies()
                    available_proxies = self.all_proxies - self.active_proxies
                    if available_proxies:
                        new_proxy = random.choice(list(available_proxies))
                        self.active_proxies.add(new_proxy)
                        new_task = asyncio.create_task(self._run_client(new_proxy))
                        tasks[new_task] = new_proxy

    async def _run_client(self, proxy: str) -> bool:
        client = WebSocketClient(proxy, self.user_id)
        return await client.connect()

def setup_logger() -> None:
    logger.remove()
    logger.add(
        "bot.log",
        format=" <level>{level}</level> | <cyan>{message}</cyan>",
        level="INFO",
        rotation="1 day"
    )
    logger.add(
        lambda msg: print(msg, end=""),
        format=" <level>{level}</level> | <cyan>{message}</cyan>",
        level="INFO",
        colorize=True
    )
async def load_user_config() -> dict:
    try:
        with open(CONFIG_FILE, "r") as config_file:
            config_data = json.load(config_file)
        return config_data if "user_ids" in config_data else {}
    except Exception as e:
        logger.error(f"❌ Error loading configuration: {str(e)}")
        return {}

async def user_input() -> dict:
    user_ids_input = input(f"{Fore.YELLOW}🔑 Enter your USER IDs (comma separated): {Style.RESET_ALL}")
    user_ids = [uid.strip() for uid in user_ids_input.split(",") if uid.strip()]
    config_data = {"user_ids": user_ids}
    with open(CONFIG_FILE, "w") as config_file:
        json.dump(config_data, config_file, indent=4)
    logger.info(f"✅ Configuration saved! USER IDs: {user_ids}")
    return config_data

async def main() -> None:
        print(f"""{Fore.RED}
⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿
⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡿⣻⣷⣒⣺⣿⣿⣿⣿⣿⣿⠿⠛⠛⠛⢿⠛⢿⣿⡟⢻⡿⠛⢻⣿⡿⠟⠛⠛⠻⢿⣿⣿⡿⠛⠛⠛⠿⣿⣿⡿⠟⠛⠛⠿⣿⣿⣿
⣿⣿⣿⣿⣿⣿⣿⣿⣿⡿⢿⣿⠏⠁⣿⣿⣿⣿⣿⣿⣿⣿⠃⢠⣾⣿⣿⣦⠀⢸⣿⡇⠀⣴⣿⣿⣿⣀⣾⣿⣿⣦⠈⣿⣿⠀⢾⣿⣷⣤⣽⣿⠁⢼⣿⣿⣦⣼⣿⣿
⣿⣿⣿⣿⣿⣿⣿⣿⠿⡇⢠⢿⠀⠀⣿⣿⣿⣿⣿⣿⣿⣿⠀⣿⣿⣿⣿⣿⠀⢸⣿⡇⢰⣿⣿⣿⣿⠟⢉⣭⣭⣅⠀⣿⣿⣦⣄⣉⡉⠙⢿⣿⣧⣤⣈⣉⠙⢿⣿⣿{Style.RESET_ALL}{Fore.WHITE}
⣿⣿⣿⣿⣿⣿⣿⠁⠀⣧⠃⢸⠀⠀⣿⣿⣿⣿⣿⣿⣿⣿⡄⠘⢿⣿⣿⠟⠀⢸⣿⡇⢸⣿⣿⣿⣯⠀⢿⣿⣿⠏⠀⣿⣿⠙⢿⣿⣿⠂⢸⣿⠉⢻⣿⣿⠇⢸⣿⣿
⣿⣿⣿⣿⣿⣿⣿⠀⢠⡇⠀⢸⠀⠀⣿⣿⣿⣿⣿⣿⣿⣿⣿⣦⣤⣤⣤⣶⠀⢸⣿⣧⣼⣿⣿⣿⣿⣦⣤⣤⣤⣾⣤⣿⣿⣷⣤⣤⣤⣴⣿⣿⣷⣤⣤⣤⣴⣿⣿⣿
⣿⣿⣿⣿⡏⠀⢸⡴⢋⡇⠀⢸⣤⣴⣿⣿⣿⣿⣿⣿⣿⣿⣿⠿⠿⠿⠿⠋⢀⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿
⣿⣿⣿⣿⣗⣲⣿⣴⣾⣷⣄⣸⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣶⣶⣶⣶⣾⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿
⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿
{Style.RESET_ALL}""")
        print(f"{Fore.CYAN}============================================================{Style.RESET_ALL}")
        print(f"{Fore.WHITE}⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿{Style.RESET_ALL}{Fore.YELLOW} Archdrop | t.me/archdrop {Style.RESET_ALL}{Fore.WHITE}⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿{Style.RESET_ALL}")
        print(f"{Fore.WHITE}⣿⣿  KALO NGEBOT GAUSAH BANYAK BACOT TENTANG RESIKO NGNTT  ⣿⣿{Style.RESET_ALL}")
        print(f"{Fore.CYAN}============================================================{Style.RESET_ALL}")
        setup_logger()

        config = await load_user_config()
        if not config or not config.get("user_ids"):
            config = await user_input()

        user_ids = config["user_ids"]

        max_proxies_input = input(f"{Fore.MAGENTA}📡 Enter the maximum number of proxies to use: {Style.RESET_ALL}")
        max_proxies = int(max_proxies_input)

        for user_id in user_ids:
            logger.info(f"🚀 Starting with USER_ID: {user_id}")
            logger.info(f"📡 Using a maximum of {max_proxies} proxies")
            logger.info(f"⏱️ Ping interval: {PING_INTERVAL} seconds")
            manager = ProxyManager(user_id)
            asyncio.create_task(manager.start(max_proxies))

        await asyncio.Event().wait()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Shutting down gracefully...")
    except Exception as e:
        logger.error(f"❌ Fatal error: {str(e)}")
