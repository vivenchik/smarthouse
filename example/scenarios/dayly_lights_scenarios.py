import asyncio
import datetime
import logging
import time

from example.configuration.config import get_config
from example.configuration.device_set import DeviceSet
from example.configuration.storage_keys import SKeys
from example.scenarios.light_utils import calc_sunrise, calc_sunset
from example.scenarios.utils import get_needed_b_t, turn_off_all, turn_on_act
from smarthouse.action_decorators import looper, scheduler
from smarthouse.storage import Storage
from smarthouse.utils import MIN, get_time, get_timedelta_now
from smarthouse.yandex_client.client import YandexClient
from smarthouse.yandex_client.device import check_and_run_async, run_async

logger = logging.getLogger("root")


@scheduler((datetime.timedelta(hours=4),))
async def night_reset_scenario():
    config = get_config()
    ya_client = YandexClient()
    storage = Storage()
    ds = DeviceSet()

    storage.put(SKeys.wc_lock, False)
    storage.put(SKeys.balcony_lock, False)
    storage.put(SKeys.exit_lock, False)
    storage.put(SKeys.evening, False)
    if config.pause:
        return None

    if (
        await ds.room_sensor.motion_time(0.5) > 60 * MIN
        and await ds.exit_sensor.motion_time(0.5) > 60 * MIN
        and await ds.wc_sensor.motion_time(0.5) > 60 * MIN
    ):
        await ya_client.run_scenario(config.silence_scenario_id)
        await asyncio.sleep(5)
        await turn_off_all()


@scheduler((datetime.timedelta(hours=8),))
async def scheduled_morning_lights_scenario():
    config = get_config()
    if config.pause:
        return 1 * MIN
    ya_client = YandexClient()
    storage = Storage()
    ds = DeviceSet()

    storage.put(SKeys.max_brightness, 1)
    storage.put(SKeys.night, False)
    if not storage.get(SKeys.lights_locked) and calc_sunrise(datetime.timedelta(minutes=0)) > get_timedelta_now():
        await ds.table_lamp.on_brightness(50).run_async()
    await ya_client.run_scenario(config.clocks_on_scenario_id)


@scheduler((datetime.timedelta(hours=10),))
async def scheduled_morning_lights_off_scenario():
    config = get_config()
    if config.pause:
        return 1 * MIN
    ds = DeviceSet()

    await run_async([lamp.off() for lamp in list(ds.alarm_lamps) + [ds.table_lamp]])


@scheduler((calc_sunset,))
async def scheduled_lights_scenario():
    config = get_config()
    if config.pause:
        return 1 * MIN
    storage = Storage()

    storage.put(SKeys.adaptive_locked, False)
    if not storage.get(SKeys.lights_locked) and not storage.get(SKeys.sleep) and not storage.get(SKeys.evening):
        logger.info("turning on lights (schedule)")
        await turn_on_act(storage.get(SKeys.clicks), storage.get(SKeys.clicks))


@looper(1, (datetime.timedelta(hours=10), calc_sunset))
async def adaptive_lights_scenario():
    config = get_config()
    if config.pause:
        return 1 * MIN
    storage = Storage()
    ds = DeviceSet()

    if (
        storage.get(SKeys.evening)
        or storage.get(SKeys.lights_locked)
        or storage.get(SKeys.adaptive_locked)
        or storage.get(SKeys.sleep)
    ):
        return 0.5

    (previous_b, previous_t, timestamp) = storage.get(SKeys.previous_b_t, (0, 0, 0))

    needed_b, needed_t = await get_needed_b_t(ds.lux_sensor, ds.room_sensor, force_interval=3, hash_seconds=0.5)
    needed_b = min(needed_b * 100, 70)

    if timestamp + 2 * MIN > time.time() and [previous_b, previous_t] == [needed_b, needed_t]:
        return

    if timestamp + 2 * MIN > time.time() and (previous_b == 0 and needed_b < 10 or previous_b < 10 and needed_b == 0):
        return

    storage.put(SKeys.previous_b_t, [needed_b, needed_t, time.time()])

    await run_async([lamp.on_temp(needed_t, needed_b) for lamp in ds.adaptive_lamps])


@looper(10)
async def alarm_scenario():
    config = get_config()
    if config.pause:
        return 1 * MIN
    storage = Storage()
    ds = DeviceSet()

    alarm = storage.get(SKeys.alarm, None)
    if alarm is None:
        return
    alarm_datetime = datetime.datetime.fromisoformat(alarm)

    if abs((alarm_datetime - get_time()).total_seconds()) < 15:
        storage.put(SKeys.stop_alarm, False)
        storage.put(SKeys.alarmed, get_time().isoformat())
        storage.put(SKeys.sleep, False)
        storage.put(SKeys.max_brightness, 1)
        storage.put(SKeys.night, False)
        storage.put(SKeys.alarm, (alarm_datetime + datetime.timedelta(days=1)).isoformat())

        if not storage.get(SKeys.lights_locked):
            await ds.curtain.open().run_async(check=False)

            if calc_sunrise(datetime.timedelta(minutes=0)) > get_timedelta_now():
                current_b = 0
                step_b = 2
                last_b = 0

                while current_b <= 30 - step_b:
                    current_b += step_b
                    last_b = current_b
                    await run_async(
                        [lamp.on_temp(temperature_k=4500, brightness=current_b) for lamp in ds.alarm_lamps],
                        check=False,
                        feature_checkable=True,
                    )
                    await asyncio.sleep(1)
                    if storage.get(SKeys.stop_alarm):
                        return

                await check_and_run_async(
                    [lamp.on_temp(temperature_k=4500, brightness=last_b) for lamp in ds.alarm_lamps]
                )
                await asyncio.sleep(10)
                if storage.get(SKeys.stop_alarm):
                    return
                await ds.curtain.open().run_async()

                await asyncio.sleep(10 * MIN)
                if storage.get(SKeys.stop_alarm):
                    return
                while current_b <= 50 - step_b:
                    current_b += step_b
                    last_b = current_b
                    await run_async(
                        [lamp.on_temp(temperature_k=4500, brightness=current_b) for lamp in ds.alarm_lamps],
                        check=False,
                        feature_checkable=True,
                    )
                    await asyncio.sleep(1)
                    if storage.get(SKeys.stop_alarm):
                        return
                await check_and_run_async(
                    [lamp.on_temp(temperature_k=4500, brightness=last_b) for lamp in ds.alarm_lamps]
                )
            else:
                await asyncio.sleep(10)
                if storage.get(SKeys.stop_alarm):
                    return
                await ds.curtain.open().run_async()
