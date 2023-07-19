from homeassistant_api import Client, Domain

from smarthouse.utils import Singleton


class HAClient(metaclass=Singleton):
    client: Client
    light: Domain

    async def init(self, ha_url: str, ha_token: str, prod: bool = False) -> None:
        if ha_token == "":
            return
        self.prod = prod
        self.client = Client(f"{ha_url}/api/", ha_token, use_async=True)
        self.light = await self.client.async_get_domain("light")  # type: ignore[assignment]
