import asyncio
import datetime
import sys
import time

from src.example.configuration.config import get_config
from src.example.configuration.device_set import DeviceSet
from src.example.configuration.storage_keys import SKeys
from src.example.scenarios.utils import get_mode_with_off, good_mo, sleep, turn_on_act
from src.lib.action_decorators import looper
from src.lib.device import run_async
from src.lib.logger import logger
from src.lib.storage import Storage
from src.lib.utils import HOUR, MIN
from src.lib.yandex_client.client import YandexClient


@looper(1)
async def worker_for_web():
    storage = Storage()
    ds = DeviceSet()

    task = await storage.tasks.get()

    if task == "sleep":
        await sleep()

    if task == "humidifier":
        if not await ds.humidifier.is_on():
            await ds.humidifier.on().run(lock_level=5, lock=datetime.timedelta(minutes=55))
            storage.put(SKeys.off_humidifier, time.time() + HOUR)
        else:
            await ds.humidifier.off().run(lock_level=5, lock=datetime.timedelta(minutes=55))

    if task == "good_mo":
        await good_mo()

    if task == "wc_off":
        storage.put(SKeys.wc_lock, not storage.get(SKeys.wc_lock, False))

    if task == "balcony_off":
        storage.put(SKeys.balcony_lock, not storage.get(SKeys.balcony_lock, False))

    if task == "exit_off":
        storage.put(SKeys.exit_lock, not storage.get(SKeys.exit_lock, False))

    if task == "evening":
        await turn_on_act(storage.get(SKeys.clicks))

    if task == "paint":
        storage.put(SKeys.paint, not storage.get(SKeys.paint, False))
        await run_async(get_mode_with_off(ds.paint))

    storage.tasks.task_done()


@looper(MIN)
async def web_utils_actions():
    config = get_config()
    if config.pause:
        return 1 * MIN
    storage = Storage()
    ds = DeviceSet()

    if storage.get(SKeys.off_humidifier) < time.time() and time.time() - storage.get(SKeys.off_humidifier) < 5 * MIN:
        await ds.humidifier.off().run()
        return 5 * MIN


@looper(5 * MIN)
async def reload_hub():
    config = get_config()
    if config.pause:
        return 1 * MIN
    ya_client = YandexClient()
    ds = DeviceSet()

    lux_sensor_stats = (
        ya_client._gss[config.lux_sensor_id].stats(ds.lux_sensor.in_quarantine())
        if config.lux_sensor_id in ya_client._gss
        else 0
    )

    if lux_sensor_stats > 0.5:
        logger.info(f"restarted hub. lux_sensor_stats: {lux_sensor_stats}")

        await ds.hub_power.off().run()
        await asyncio.sleep(10)
        await ds.hub_power.on().run()

        return 60 * MIN


async def not_prod():
    config = get_config()

    if not config.prod:
        await asyncio.sleep(20 * MIN)
        logger.error("This is not prod")
        sys.exit(0)
