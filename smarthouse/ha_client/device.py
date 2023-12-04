from typing import Optional

from smarthouse.ha_client.client import HAClient


class Device:
    def __init__(self, entity_id, name=""):
        self.entity_id = entity_id
        self.name = name
        self.ha_client = HAClient()

    async def info(self, hash_seconds: float | None = 1):
        return await self.ha_client.device_info(self.entity_id, hash_seconds=hash_seconds)

    async def check_property(self, entity_id, property_name, process_last=False, hash_seconds: float | None = 1):
        return (
            await self.ha_client.check_property(
                entity_id or self.entity_id, property_name, process_last=process_last, hash_seconds=hash_seconds
            )
        )[0]

    def in_quarantine(self):
        return self.ha_client.quarantine_in(self.entity_id)

    def quarantine(self):
        return self.ha_client.quarantine_get(self.entity_id)


class YeelinkLamp(Device):
    async def is_on(self):
        return await self.ha_client.check_property() == "on"

    async def on(self):
        return await self.ha_client.domains["light"].turn_on(entity_id=self.entity_id)  # todo

    async def off(self):
        return await self.ha_client.domains["light"].turn_off(entity_id=self.entity_id)  # todo

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

        return await self.ha_client.domains["light"].turn_on(entity_id=self.entity_id, brightness=brightness)  # todo

    async def on_temp(self, temperature_k=4500, brightness=100):
        brightness = self._fix_brightness(brightness)

        if temperature_k is None or brightness == 0 or brightness is None:
            return await self.on_brightness(brightness)

        temperature_k = self._fix_temperature_k(temperature_k)

        return await self.ha_client.domains["light"].turn_on(
            entity_id=self.entity_id, brightness=brightness, kelvin=temperature_k
        )  # todo

    # async def on_rgb(self, rgb, brightness=100):
    #     brightness = self._fix_brightness(brightness)
    #
    #     if rgb is None or brightness == 0 or brightness is None:
    #         return await self.on_brightness(brightness)
    #
    #     return await self.ha_client.light.turn_on(entity_id=self.entity_id, brightness=brightness, rgb_color=rgb)


class YeelinkAirCleaner(Device):
    async def humidity(self):
        state = await self.check_property("sensor.xiaomi_smart_air_purifier_4_humidity", "humidity")  # todo
        return int(state)  # todo
