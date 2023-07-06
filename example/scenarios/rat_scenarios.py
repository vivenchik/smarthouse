import asyncio
import datetime

from example.configuration.config import get_config
from example.configuration.device_set import DeviceSet
from example.configuration.storage_keys import SKeys
from example.main_simple import calc_sunset
from example.scenarios.utils import turn_on_act
from smarthouse.action_decorators import looper
from smarthouse.device import run
from smarthouse.storage import Storage
from smarthouse.utils import MIN, get_time, get_timedelta_now
from smarthouse.yandex_client.client import YandexClient


@looper(1)
async def rat_darkness():
    config = get_config()
    if config.pause:
        return 1 * MIN
    ya_client = YandexClient()
    storage = Storage()
    ds = DeviceSet()

    if not storage.get(SKeys.rat_game):
        return

    if storage.get(SKeys.rat_game_finalized):
        return

    rat_game_start = storage.get(SKeys.rat_game_start, None)
    if rat_game_start is None:
        return
    rat_game_start_datetime = datetime.datetime.fromisoformat(rat_game_start)

    if abs((rat_game_start_datetime - get_time()).total_seconds()) < MIN:
        return

    all_lamps = list(ds.all_lamps) + [ds.wc_1, ds.wc_2, ds.lamp_e_1, ds.lamp_e_2, ds.lamp_e_3]

    for lamp in all_lamps:
        if await lamp.is_on() and not lamp.in_quarantine():
            return

    await run([ds.table_lamp.on(), ds.bed_lamp.on()], lock_level=15)
    if not ds.table_lamp.in_quarantine() or not ds.bed_lamp.in_quarantine():
        return

    rat_lock = storage.get(SKeys.rat_lock, None)
    if rat_lock is not None:
        rat_lock_datetime = datetime.datetime.fromisoformat(rat_lock)
        if rat_lock_datetime > get_time():
            await asyncio.sleep((rat_lock_datetime - get_time()).total_seconds())

    await ya_client.run_scenario(config.rat_final_scenario_id)
    await asyncio.sleep(30)
    ya_client.locks_reset()
    await run([ds.table_lamp.off(), ds.bed_lamp.off()])
    if get_timedelta_now() >= calc_sunset() or storage.get(SKeys.evening):
        await turn_on_act(storage.get(SKeys.clicks))
    storage.put(SKeys.rat_game_finalized, True)


@looper(1)
async def rat_support():
    config = get_config()
    if config.pause:
        return 1 * MIN
    ya_client = YandexClient()
    storage = Storage()

    if not storage.get(SKeys.rat_game):
        return

    rat_game_start = storage.get(SKeys.rat_game_start, None)
    if rat_game_start is None:
        return
    rat_game_start_datetime = datetime.datetime.fromisoformat(rat_game_start)

    offsets = [
        (datetime.timedelta(minutes=10), config.rat_1_scenario_id),
        (datetime.timedelta(minutes=15), config.rat_15_scenario_id),
        (datetime.timedelta(minutes=20), config.rat_2_scenario_id),
        (datetime.timedelta(minutes=30), config.rat_3_scenario_id),
        (datetime.timedelta(minutes=40), config.rat_4_scenario_id),
        (datetime.timedelta(minutes=45), config.rat_45_scenario_id),
        (datetime.timedelta(minutes=50), config.rat_5_scenario_id),
    ]

    for offset, scenario_id in offsets:
        if abs((rat_game_start_datetime + offset - get_time()).total_seconds()) < MIN:
            storage.put(SKeys.rat_lock, (get_time() + datetime.timedelta(seconds=30)).isoformat())
            await ya_client.run_scenario(scenario_id)
            return 2 * MIN

    if abs((rat_game_start_datetime + datetime.timedelta(minutes=60) - get_time()).total_seconds()) < MIN:
        storage.put(SKeys.rat_lock, (get_time() + datetime.timedelta(seconds=30)).isoformat())
        await ya_client.run_scenario(config.rat_time_scenario_id)
        storage.put(SKeys.rat_game, False)
