import asyncio
import datetime
import logging
import sys

from example.configuration.config import get_config
from example.configuration.device_set import DeviceSet
from example.configuration.storage_keys import SKeys
from example.scenarios.utils import get_mode_with_off, good_mo, sleep, turn_on_act
from smarthouse.action_decorators import looper
from smarthouse.storage import Storage
from smarthouse.utils import MIN
from smarthouse.yandex_client.client import YandexClient
from smarthouse.yandex_client.device import run_async

logger = logging.getLogger("root")


@looper(1)
async def worker_for_web_scenario():
    storage = Storage()
    ds = DeviceSet()

    task = await storage.tasks.get()

    if task == "sleep":
        await sleep()

    if task == "good_mo":
        await good_mo()

    if task == "wc_off":
        storage.put(SKeys.wc_lock, not storage.get(SKeys.wc_lock, False))

    if task == "balcony_off":
        storage.put(SKeys.balcony_lock, not storage.get(SKeys.balcony_lock, False))

    if task == "exit_off":
        storage.put(SKeys.exit_lock, not storage.get(SKeys.exit_lock, False))

    if task == "evening":
        storage.put(SKeys.evening, True)
        await turn_on_act(storage.get(SKeys.clicks), storage.get(SKeys.clicks))

    if task == "paint":
        storage.put(SKeys.paint, not storage.get(SKeys.paint, False))
        await run_async(get_mode_with_off(ds.paint))

    if task == "air_cleaner_off":
        await ds.air_cleaner.off().run_async(lock_level=10, lock=datetime.timedelta(hours=3))

    storage.tasks.task_done()


@looper(5 * MIN)
async def reload_hub_scenario():
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


async def not_prod_scenario():
    config = get_config()

    if not config.prod:
        await asyncio.sleep(20 * MIN)
        logger.error("This is not prod")
        await Storage()._write_storage(force=True)
        sys.exit(0)
