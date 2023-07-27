from typing import Optional

from smarthouse.ha_client.client import HAClient


class Device:
    def __init__(self, entity_id, name=""):
        self.entity_id = entity_id
        self.name = name
        self.ha_client = HAClient()

    async def get_state(self, entity_id=None):
        return (await self.ha_client.client.async_get_entity(entity_id=entity_id or self.entity_id)).state


class YeelinkLamp(Device):
    async def is_on(self):
        return (await self.get_state()).state == "on"

    async def on(self):
        return await self.ha_client.light.turn_on(entity_id=self.entity_id)

    async def off(self):
        return await self.ha_client.light.turn_off(entity_id=self.entity_id)

    def _fix_temperature_k(self, temperature_k):
        return min(6500, max(1500, int(temperature_k))) if temperature_k is not None else None

    def _fix_brightness(self, brightness):
        return min(100, max(0, int(brightness))) if brightness is not None else None

    async def on_brightness(self, brightness: Optional[int] = 100):
        if brightness is None:
            return await self.on()

        brightness = self._fix_brightness(brightness)

        if brightness == 0:
            return await self.off()

        return await self.ha_client.light.turn_on(entity_id=self.entity_id, brightness=brightness)

    async def on_temp(self, temperature_k=4500, brightness=100):
        brightness = self._fix_brightness(brightness)

        if temperature_k is None or brightness == 0 or brightness is None:
            return await self.on_brightness(brightness)

        temperature_k = self._fix_temperature_k(temperature_k)

        return await self.ha_client.light.turn_on(entity_id=self.entity_id, brightness=brightness, kelvin=temperature_k)

    # async def on_rgb(self, rgb, brightness=100):
    #     brightness = self._fix_brightness(brightness)
    #
    #     if rgb is None or brightness == 0 or brightness is None:
    #         return await self.on_brightness(brightness)
    #
    #     return await self.ha_client.light.turn_on(entity_id=self.entity_id, brightness=brightness, rgb_color=rgb)


class YeelinkAirCleaner(Device):
    async def humidity(self):
        return int((await self.get_state("sensor.xiaomi_smart_air_purifier_4_humidity")).state)  # todo
