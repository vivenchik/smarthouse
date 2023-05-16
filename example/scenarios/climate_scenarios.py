import asyncio
import time

from example.configuration.config import get_config
from example.configuration.device_set import DeviceSet
from example.configuration.storage_keys import SKeys
from smarthouse.action_decorators import looper
from smarthouse.device import run
from smarthouse.storage import Storage
from smarthouse.utils import HOUR, MIN
from smarthouse.yandex_client.client import YandexClient


@looper(10)
async def wc_hydro_actions():
    config = get_config()
    if config.pause:
        return 1 * MIN
    ya_client = YandexClient()
    storage = Storage()
    ds = DeviceSet()
    last_hydro = time.time() - storage.get(SKeys.last_hydro)

    wc_term_humidity = await ds.wc_term.humidity()
    if (
        not wc_term_humidity.quarantine
        and (last_hydro > HOUR + 30 * MIN or wc_term_humidity.result > 75)
        and wc_term_humidity.result > 55
        and not await ds.air.is_on(10)
        and (await ds.wc_1.is_on() or await ds.wc_2.is_on())
    ):
        await run([ds.air.on(), ds.humidifier.on("high")])
        storage.put(SKeys.last_hydro, time.time())

    if last_hydro < HOUR + 5 * MIN:
        exit_sensor = await ds.exit_sensor.motion_time()
        if (exit_sensor < 15 or await ds.room_sensor.motion_time() < 15) and (
            await ds.air.is_on(10)
            or ya_client.locks_in(config.air_id)
            and ya_client.locks_get(config.air_id).level == 10
            and ya_client.locks_get(config.air_id).timestamp > time.time()
        ):
            await ds.humidifier.off().run()
        if exit_sensor < 15 and await ds.air.is_on(10):
            while True:
                wc_term_humidity = await ds.wc_term.humidity()
                if wc_term_humidity.quarantine or wc_term_humidity.result <= 60:
                    break
                await asyncio.sleep(30)
            await ds.air.off().run()
        elif HOUR < last_hydro < HOUR + 15:
            await ds.air.off().run()


@looper(MIN)
async def dry_actions():
    config = get_config()
    if config.pause:
        return 1 * MIN
    ds = DeviceSet()

    air_cleaner_humidity = await ds.air_cleaner.humidity()
    if not air_cleaner_humidity.quarantine and air_cleaner_humidity.result < 25:
        await ds.humidifier.on().run()
        if await ds.humidifier.is_on():
            await asyncio.sleep(HOUR)
            await ds.humidifier.off().run()


@looper(MIN)
async def water_level_checker():
    storage = Storage()
    ds = DeviceSet()

    water_level = await ds.humidifier.water_level()

    if water_level <= 30 and not storage.get(SKeys.water_notified):
        await storage.messages_queue.put("please insert water")
        storage.put(SKeys.water_notified, True)

    if water_level > 50 and storage.get(SKeys.water_notified):
        storage.put(SKeys.water_notified, False)
