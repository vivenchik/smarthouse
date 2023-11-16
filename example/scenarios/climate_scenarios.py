import asyncio
import logging
import time

from example.configuration.config import get_config
from example.configuration.device_set import DeviceSet
from example.configuration.storage_keys import SKeys
from smarthouse.action_decorators import looper
from smarthouse.storage import Storage
from smarthouse.utils import HOUR, MIN

logger = logging.getLogger("root")


@looper(10)
async def wc_hydro_scenario():
    config = get_config()
    if config.pause:
        return 1 * MIN
    storage = Storage()
    ds = DeviceSet()
    last_hydro = time.time() - storage.get(SKeys.last_hydro)

    wc_term_humidity = await ds.wc_term.humidity()
    if (
        not wc_term_humidity.quarantine
        and (last_hydro > HOUR + 30 * MIN or wc_term_humidity.result > 75)
        and wc_term_humidity.result > 60
        and not await ds.air.is_on(10)
        and (await ds.wc_1.is_on() or await ds.wc_2.is_on())
    ):
        await ds.air.on().run_async()
        storage.put(SKeys.last_hydro, time.time())

    if last_hydro < HOUR + 5 * MIN:
        exit_sensor = await ds.exit_sensor.motion_time()
        if exit_sensor < 15 and await ds.air.is_on(10):
            while True:
                wc_term_humidity = await ds.wc_term.humidity()
                if wc_term_humidity.quarantine or wc_term_humidity.result <= 60:
                    break
                await asyncio.sleep(30)
            await ds.air.off().run_async()
        elif HOUR < last_hydro < HOUR + 15:
            await ds.air.off().run_async()


@looper(10 * MIN)
async def water_level_checker_scenario():
    storage = Storage()
    ds = DeviceSet()

    water_level = await ds.humidifier_new.water_level()

    if water_level <= 20 and not storage.get(SKeys.water_notified):
        await storage.messages_queue.put({"message": "please insert water"})
        storage.put(SKeys.water_notified, True)

    if water_level > 80 and storage.get(SKeys.water_notified):
        storage.put(SKeys.water_notified, False)


@looper(MIN)
async def bad_humidity_checker_scenario():
    storage = Storage()
    ds = DeviceSet()

    if storage.get(SKeys.lights_locked):
        return

    wc_term_humidity = await ds.wc_term.humidity()
    air_cleaner_humidity = await ds.air_cleaner.humidity()
    humidifier_new_humidity = await ds.humidifier_new.humidity()
    max_humidity = max(
        wc_term_humidity.result if not wc_term_humidity.quarantine else 0,
        air_cleaner_humidity.result if not air_cleaner_humidity.quarantine else 0,
        humidifier_new_humidity.result if not humidifier_new_humidity.quarantine else 0,
    )
    min_humidity_home = min(
        air_cleaner_humidity.result if not air_cleaner_humidity.quarantine else 100,
        humidifier_new_humidity.result if not humidifier_new_humidity.quarantine else 100,
    )

    if max_humidity < 35 or min_humidity_home < 30:
        logger.info("turning on humidifier")
        await ds.humidifier_new.on().run_async()
        storage.put(SKeys.humidifier_offed, 0)
    elif (
        max_humidity >= 45
        and time.time() - storage.get(SKeys.humidifier_offed) > HOUR
        and await ds.humidifier_new.is_on()
    ):
        logger.info("turning off humidifier")
        await ds.humidifier_new.off().run_async(check=storage.get(SKeys.humidifier_offed) != 0)
        storage.put(SKeys.humidifier_offed, time.time())


@looper(10 * MIN)
async def air_cleaner_checker_scenario():
    ds = DeviceSet()

    if not await ds.air_cleaner.is_on():
        await asyncio.sleep(HOUR)
        await ds.air_cleaner.on().run_async()
