import asyncio
import datetime
import random
import time
from typing import Union

from example.configuration.config import get_config
from example.configuration.device_set import DeviceSet
from example.configuration.storage_keys import SKeys
from example.scenarios.light_utils import calc_sunset
from example.scenarios.utils import (
    check_and_fix_act,
    find_current_pos_modes_order,
    get_modes_order,
    get_possible_colors,
    get_possible_white_colors,
    get_zone,
    good_mo,
    light_ons,
    sleep,
    turn_off_all,
    turn_on_act,
)
from smarthouse.action_decorators import looper, scheduler
from smarthouse.storage import Storage
from smarthouse.utils import MIN, get_time, get_timedelta_now, hsv_to_rgb
from smarthouse.yandex_client.client import YandexClient
from smarthouse.yandex_client.device import HSVLamp, RGBLamp, TemperatureLamp, run_async


@looper(1)
async def random_colors_scenario(
    lamp_groups: tuple[tuple[Union[HSVLamp, RGBLamp, TemperatureLamp], ...], ...], jump_time, rand=(15, 60), sync=False
):
    config = get_config()
    if config.pause:
        return 1 * MIN
    storage = Storage()

    if storage.get(SKeys.random_colors) and not storage.get(SKeys.lights_locked) and not storage.get(SKeys.sleep):
        if (rc_lock := storage.get(SKeys.rc_lock)) > time.time():
            diff = rc_lock - time.time()
            return diff + (random.randint(5, 10) if diff > 1 else 0)

        zone = get_zone()
        actions = []
        if not sync:
            storage.put(SKeys.rc_lock, time.time() + 1)
            for lamp_group in lamp_groups:
                if storage.get(SKeys.random_colors_mode) == 0:
                    possible_colors = await get_possible_colors(len(lamp_group), zone)
                    for i in range(len(lamp_group)):
                        lamp = lamp_group[i]
                        if isinstance(lamp, HSVLamp):
                            actions.append(lamp.on_hsv(possible_colors[i]))
                        if isinstance(lamp, RGBLamp):
                            actions.append(lamp.on_rgb(hsv_to_rgb(possible_colors[i])))
                else:
                    possible_colors = get_possible_white_colors(len(lamp_group))
                    for i in range(len(lamp_group)):
                        lamp = lamp_group[i]
                        actions.append(
                            lamp.on_temp(temperature_k=possible_colors[i][1], brightness=possible_colors[i][0])
                        )
        else:
            if zone is not None:
                return MIN
            storage.put(SKeys.rc_lock, time.time() + 10)
            if storage.get(SKeys.random_colors_mode) == 0:
                possible_colors = await get_possible_colors(max([len(lamp_group) for lamp_group in lamp_groups]))
                for lamp_group in lamp_groups:
                    for i in range(len(lamp_group)):
                        lamp = lamp_group[i]
                        if isinstance(lamp, HSVLamp):
                            actions.append(lamp.on_hsv(possible_colors[i]))
                        if isinstance(lamp, RGBLamp):
                            actions.append(lamp.on_rgb(hsv_to_rgb(possible_colors[i])))
            else:
                possible_colors = get_possible_white_colors(max([len(lamp_group) for lamp_group in lamp_groups]))
                for lamp_group in lamp_groups:
                    for i in range(len(lamp_group)):
                        lamp = lamp_group[i]
                        actions.append(
                            lamp.on_temp(temperature_k=possible_colors[i][1], brightness=possible_colors[i][0])
                        )

        await run_async(actions)

        if len(lamp_groups) > 1:
            return random.randint(*rand)
        if jump_time[0] <= get_time().second < jump_time[1]:
            return random.randint(2, 3)
        if random.randint(1, 100) > 5:
            return random.randint(*rand)


@looper(1)
async def button_scenario():
    config = get_config()
    if config.pause:
        return 1 * MIN
    ya_client = YandexClient()
    storage = Storage()
    ds = DeviceSet()

    last_click = max(storage.get(SKeys.last_click), storage.get(SKeys.startup))
    state_button, button_time = await ds.button.button(None)

    storage_commands = sorted(
        [(key[len("__click_") :], value) for key, value in storage.items() if key.startswith("__click")],
        key=lambda x: x[1],
    )
    button_clicked = button_time - last_click > 0.01
    storage_button_clicked = storage_commands and storage_commands[0][1] - last_click > 0.01

    if button_clicked or storage_button_clicked:
        storage.put(SKeys.last_click, max(button_time, time.time()))
        storage.put(SKeys.lights_locked, False)
        storage.put(SKeys.paint, False)

        if not button_clicked and storage_button_clicked:
            state_button = storage_commands[0][0]
            button_time = storage_commands[0][1]

        storage.put(SKeys.last_click, max(button_time, time.time()))

        if state_button == "double_click":
            lamps_to_off = set(ds.all_lamps) - set(lamp for mode in ds.lamp_groups for lamp in mode)
            await run_async([lamp.off() for lamp in lamps_to_off])

            if not storage.get(SKeys.random_colors):
                storage.put(SKeys.random_colors_mode, 0)
            else:
                storage.put(SKeys.random_colors_mode, (storage.get(SKeys.random_colors_mode) + 1) % 2)
            storage.put(SKeys.random_colors, True)
            storage.put(SKeys.random_colors_passive, True)
            return

        if state_button == "long_press":
            if datetime.timedelta(hours=10) < get_timedelta_now() < calc_sunset():
                storage.put(SKeys.adaptive_locked, True)
            await turn_off_all()
            return

        random_colors = storage.get(SKeys.random_colors)
        storage.put(SKeys.random_colors, False)

        if random_colors:
            return

        if datetime.timedelta(hours=10) < get_timedelta_now() < calc_sunset():
            for lamp in ds.adaptive_lamps:
                ya_client.locks_remove(lamp.device_id)
            storage.put(SKeys.adaptive_locked, False)
            return

        clicks = storage.get(SKeys.clicks)
        skip = storage.get(SKeys.skip)

        light_on = button_time - last_click < 10 or await light_ons()
        if not light_on or light_on and storage.get(SKeys.random_colors_passive):
            skip = -1
        else:
            modes_order = get_modes_order()
            if button_time - last_click < MIN:
                current_pos = find_current_pos_modes_order(modes_order, clicks)
                clicks = (current_pos + 1) % len(ds.modes)
                if clicks == skip:
                    clicks = (current_pos + 2) % len(ds.modes)
                    skip = -1
            else:
                skip = clicks % len(ds.modes)
                clicks = modes_order[1] if skip == modes_order[0] else modes_order[0]

        await turn_on_act(clicks, skip, check=False, feature_checkable=True)
        storage.put(SKeys.button_checked, False)
        storage.put(SKeys.random_colors_passive, False)
        storage.put(SKeys.clicks, clicks)
        storage.put(SKeys.skip, skip)

    after_last_click = time.time() - max(storage.get(SKeys.last_click), storage.get(SKeys.startup))
    clicks = storage.get(SKeys.clicks)
    if (
        not storage.get(SKeys.button_checked)
        and after_last_click > 5
        and not storage.get(SKeys.random_colors_passive)
        and await light_ons()
    ):
        await check_and_fix_act(clicks, clicks)
        storage.put(SKeys.button_checked, True)

    if after_last_click < 15:
        return 0.1
    if after_last_click < 10 * MIN:
        return 0.5
    if (
        storage.get(SKeys.lights_locked)
        or storage.get(SKeys.sleep)
        or (after_last_click > 30 * MIN and await ds.room_sensor.motion_time() > 30 * MIN)
    ):
        return 10


@looper(1)
async def button_sleep_actions_scenario():
    config = get_config()
    if config.pause:
        return 1 * MIN
    ya_client = YandexClient()
    storage = Storage()
    ds = DeviceSet()

    last_click_b_2 = max(storage.get(SKeys.last_click_b_2), storage.get(SKeys.startup))
    state_button, button_time = await ds.button_2.button(None)

    if button_time - last_click_b_2 > 0.01:
        storage.put(SKeys.last_click_b_2, max(button_time, time.time()))

        alarmed_datetime = datetime.datetime.fromisoformat(storage.get(SKeys.alarmed, "2022-11-27T00:00:00+03:00"))
        if abs((get_time() - alarmed_datetime).total_seconds()) < 15 * MIN:
            storage.put(SKeys.stop_alarm, True)
            await run_async([lamp.off() for lamp in ds.alarm_lamps], lock_level=8, lock=datetime.timedelta(minutes=15))
            await ds.curtain.close().run_async(check=False)
            await ya_client.run_scenario(config.silence_scenario_id)
            await asyncio.sleep(10)
            await ds.curtain.close().run_async(lock_level=8, lock=datetime.timedelta(minutes=15))
            return

        if state_button == "click":
            if storage.get(SKeys.sleep):
                await good_mo()
            else:
                await sleep()

    if storage.get(SKeys.lights_locked):
        return 10


@scheduler((datetime.timedelta(hours=4),))
async def div_modes_stats_scenario():
    storage = Storage()
    ds = DeviceSet()

    modes_stats = storage.get(SKeys.modes_stats, [0] * len(ds.modes))
    modes_stats = [mode_stats * 0.95 for mode_stats in modes_stats]
    storage.put(SKeys.modes_stats, modes_stats)
