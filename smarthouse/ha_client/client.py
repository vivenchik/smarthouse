from homeassistant_api import Client, Domain

from smarthouse.utils import Singleton


class HAClient(metaclass=Singleton):
    client: Client
    light: Domain

    async def init(self, ha_url: str = "", ha_token: str = "", prod: bool = False) -> None:
        if ha_url == "":
            return
        self.prod = prod
        self.client = Client(ha_url, ha_token, use_async=True)
        self.light = await self.client.async_get_domain("light")  # type: ignore[assignment]
