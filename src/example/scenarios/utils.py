import asyncio
import datetime
import random
import time
from typing import Optional

from src.example.configuration.config import get_config
from src.example.configuration.device_set import DeviceSet
from src.example.configuration.storage_keys import SKeys
from src.lib.device import LuxSensor, check_and_run_async, run_async
from src.lib.storage import Storage
from src.lib.utils import MIN, get_time, get_timedelta_now
from src.lib.yandex_client.client import YandexClient


def get_act(clicks):
    ds = DeviceSet()
    modes = ds.modes
    current_mode = modes[clicks % len(modes)]
    return current_mode


def get_mode_with_off(current_mode: list):
    ds = DeviceSet()
    current_ids = [lamp.device_id for lamp in current_mode]
    current_mode_off = [lamp.off() for lamp in ds.all_lamps if lamp.device_id not in current_ids]

    return current_mode + current_mode_off


async def turn_on_act(clicks, check: bool = True, feature_checkable: bool = False):
    current_mode = get_act(clicks)
    await run_async(get_mode_with_off(current_mode), check=check, feature_checkable=feature_checkable)


async def check_and_fix_act(clicks):
    current_mode = get_act(clicks)
    await check_and_run_async(get_mode_with_off(current_mode))


async def light_ons(hash_seconds=1):
    ds = DeviceSet()
    return (
        await ds.table_lamp.is_on(hash_seconds=hash_seconds)
        or await ds.left_lamp.is_on(hash_seconds=hash_seconds)
        or await ds.balcony_lamp.is_on(hash_seconds=hash_seconds)
        or await ds.lamp_k_1.is_on(hash_seconds=hash_seconds)
        or await ds.bed_lights.is_on(hash_seconds=hash_seconds)
        or await ds.lamp_g_1.is_on(hash_seconds=hash_seconds)
        or await ds.piano_lamp.is_on(hash_seconds=hash_seconds)
        or await ds.sofa_lamp.is_on(hash_seconds=hash_seconds)
    )


async def light_colored(hash_seconds=1):
    ds = DeviceSet()
    return (
        await ds.lamp_k_1.color_setting(hash_seconds=hash_seconds) == "hsv"
        and await ds.left_lamp.color_setting(hash_seconds=hash_seconds) == "hsv"
        and await ds.table_lamp.color_setting(hash_seconds=hash_seconds) == "rgb"
    )


async def get_needed_b_t(sensor: LuxSensor, second_sensor: Optional[LuxSensor] = None):
    config = get_config()
    storage = Storage()
    adaptive_temps = config.adaptive_temps

    state_lux = await sensor.illumination()
    if not state_lux.quarantine:
        result_state_lux = state_lux
    else:
        if second_sensor is None:
            if sensor.quarantine().timestamp + 5 * MIN > time.time():
                result_state_lux = await sensor.illumination(proceeded_last=True)
            else:
                result_state_lux = state_lux
        else:
            second_state_lux = await second_sensor.illumination()
            if not second_state_lux.quarantine:
                result_state_lux = second_state_lux
            else:
                if sensor.quarantine().timestamp + 5 * MIN > time.time():
                    result_state_lux = await sensor.illumination(proceeded_last=True)
                elif second_sensor.quarantine().timestamp + 5 * MIN > time.time():
                    result_state_lux = await second_sensor.illumination(proceeded_last=True)
                else:
                    result_state_lux = state_lux

    needed_b = 1 - min(result_state_lux.result, 200) / 200
    needed_b = min(needed_b, storage.get(SKeys.max_brightness, 1))

    adaptive_interval = [
        datetime.timedelta(hours=config.adaptive_interval[0]),
        datetime.timedelta(hours=config.adaptive_interval[1]),
    ]
    if adaptive_interval[0] > adaptive_interval[1]:
        adaptive_interval[1] += datetime.timedelta(days=1)

    timedelta_now = get_timedelta_now()
    if adaptive_interval[0] <= timedelta_now < adaptive_interval[1]:
        step = (adaptive_interval[1] - adaptive_interval[0]).seconds / len(adaptive_temps)
        current_delta = (timedelta_now - adaptive_interval[0]).seconds
        needed_t_ind = int(current_delta / step)
    elif adaptive_interval[1] <= timedelta_now or timedelta_now < datetime.timedelta(hours=6):
        needed_t_ind = len(adaptive_temps) - 1
    else:
        needed_t_ind = 0

    needed_t = adaptive_temps[needed_t_ind]
    needed_b *= 1 - 0.05 * needed_t_ind

    return needed_b, needed_t


def get_possible_white_colors(count):
    possible_temps = (6500, 5600, 4500, 3400)
    temp = random.choice(possible_temps)
    return [(random.randint(10, 40) if random.randint(1, 100) <= 50 else 0, temp) for _ in range(count)]


async def get_possible_colors(count, zone=None):
    config = get_config()
    all_colors = dict(enumerate(config.colors.values()))
    if zone is None:
        zone = 0, len(all_colors)
    color_set = set(
        list(all_colors.keys())[zone[0] : zone[1]]
        if zone[0] < zone[1]
        else list(all_colors.keys())[zone[0] :] + list(all_colors.keys())[: zone[1]]
    )
    color_items = []
    while len(color_set) != 0:
        ind = random.choice(list(color_set))
        color_set.remove(ind)

        if all_colors[ind] != (0, 0, 0):
            color_items.append((ind, all_colors[ind]))
            color_set.discard(ind - 1)
            color_set.discard(ind + 1)

    result = [
        (
            min(max(color[1][0] + random.randint(-(color[1][0] // 30), max(color[1][0] // 30, 1)), 0), 360),
            color[1][1],
            color[1][2],
        )
        for color in sorted(color_items)
    ]

    start = random.randint(0, len(result) - 1)
    rounded_result = result[start : start + count] + result[: max(count + start - len(result), 0)]

    if bool(random.randint(0, 1)):
        rounded_result.reverse()
    return rounded_result


def get_zone():
    zones = [
        (0, 8),
        (4, 11),
        (8, 15),
        (13, 20),
        (17, 3),
    ]

    minute15 = get_time().minute % 20
    if minute15 % 4 == 0:
        return zones[minute15 // 4]


async def turn_off_all():
    storage = Storage()
    ds = DeviceSet()
    storage.put(SKeys.random_colors_passive, False)
    storage.put(SKeys.random_colors, False)
    await run_async([lamp.off() for lamp in ds.all_lamps], lock_level=11, lock=datetime.timedelta(seconds=0))


async def sleep():
    config = get_config()
    ya_client = YandexClient()
    storage = Storage()
    ds = DeviceSet()

    storage.put(SKeys.sleep, True)
    storage.put(SKeys.night, True)
    storage.put(SKeys.max_brightness, 0.1)
    storage.put(SKeys.random_colors, False)
    storage.put(SKeys.random_colors_passive, False)
    ya_client.locks_reset()
    await ds.curtain.close().run_async(check=False, feature_checkable=True)
    await turn_off_all()
    await run_async([ds.humidifier.off(), ds.air.off()])
    await ya_client.run_scenario(config.clocks_off_scenario_id)
    await asyncio.sleep(3)
    await ya_client.run_scenario(config.silence_scenario_id)
    await ds.curtain.close().run_async()


async def good_mo():
    config = get_config()
    ya_client = YandexClient()
    storage = Storage()
    ds = DeviceSet()

    storage.put(SKeys.sleep, False)
    storage.put(SKeys.max_brightness, 1)
    storage.put(SKeys.night, False)
    ya_client.locks_reset()
    await ds.curtain.open().run_async(check=False, feature_checkable=True)
    await ya_client.run_scenario(config.clocks_on_scenario_id)
    await asyncio.sleep(3)
    await ds.curtain.open().run_async()
