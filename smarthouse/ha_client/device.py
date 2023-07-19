from smarthouse.ha_client.client import HAClient


class Device:
    def __init__(self, entity_id):
        self.entity_id = entity_id
        self.ha_client = HAClient()


class Lamp(Device):
    async def on(self):
        await self.ha_client.light.turn_on(entity_id=self.entity_id)

    async def off(self):
        await self.ha_client.light.turn_off(entity_id=self.entity_id)
