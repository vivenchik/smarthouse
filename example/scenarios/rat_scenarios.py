import datetime

from example.configuration.config import get_config
from example.configuration.device_set import DeviceSet
from example.configuration.storage_keys import SKeys
from smarthouse.action_decorators import looper
from smarthouse.storage import Storage
from smarthouse.utils import MIN, get_time
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

    await ds.table_lamp.on().run(lock_level=15)
    if await ds.table_lamp.is_on() and not ds.table_lamp.in_quarantine():
        return

    await ds.bed_lamp.on().run(lock_level=15)
    if await ds.bed_lamp.is_on() and not ds.bed_lamp.in_quarantine():
        return

    await ds.balcony_lamp.on().run(lock_level=15)
    if await ds.balcony_lamp.is_on() and not ds.balcony_lamp.in_quarantine():
        return

    await ya_client.run_scenario(config.rat_final_scenario_id)
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
        (datetime.timedelta(minutes=20), config.rat_2_scenario_id),
        (datetime.timedelta(minutes=30), config.rat_3_scenario_id),
        (datetime.timedelta(minutes=40), config.rat_4_scenario_id),
        (datetime.timedelta(minutes=50), config.rat_5_scenario_id),
    ]

    for offset, scenario_id in offsets:
        if abs((rat_game_start_datetime + offset - get_time()).total_seconds()) < MIN:
            await ya_client.run_scenario(scenario_id)
            return 2 * MIN

    if abs((rat_game_start_datetime + datetime.timedelta(minutes=60) - get_time()).total_seconds()) < MIN:
        await ya_client.run_scenario(config.rat_time_scenario_id)
        storage.put(SKeys.rat_game, False)
