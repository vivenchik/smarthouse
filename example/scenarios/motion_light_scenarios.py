import asyncio
import datetime
import time

from example.configuration.config import get_config
from example.configuration.device_set import DeviceSet
from example.configuration.storage_keys import SKeys
from example.scenarios.light_utils import calc_sunrise, calc_sunset
from example.scenarios.utils import get_act, get_needed_b_t
from smarthouse.action_decorators import looper
from smarthouse.storage import Storage
from smarthouse.utils import HOUR, MIN, get_timedelta_now
from smarthouse.yandex_client.device import run


@looper(0.5)
async def lights_corridor_on_actions():
    config = get_config()
    if config.pause:
        return 1 * MIN
    storage = Storage()
    ds = DeviceSet()

    if not storage.get(SKeys.exit_lock):
        if (
            not storage.get(SKeys.lights_locked)
            and await ds.exit_sensor.motion_time(None) < 60
            or storage.get(SKeys.lights_locked)
            and await ds.exit_door.open_time() < 60
        ):
            needed_b, needed_t = await get_needed_b_t(ds.exit_sensor, ds.lux_sensor)
            max_b = 70 if datetime.timedelta(hours=8) < get_timedelta_now() < calc_sunset() else 40
            needed_b = min(needed_b * 100, max_b)

            await run([lamp.on_temp(needed_t, needed_b) for lamp in [ds.lamp_e_1, ds.lamp_e_2, ds.lamp_e_3]])

            return 3 * MIN


@looper(0.5)
async def lights_wc_on_actions():
    config = get_config()
    if config.pause:
        return 1 * MIN
    storage = Storage()
    ds = DeviceSet()

    if (
        not storage.get(SKeys.lights_locked)
        and not storage.get(SKeys.wc_lock)
        and not storage.get(SKeys.night)
        and (await ds.exit_sensor.motion_time(None) < 60 or await ds.wc_sensor.motion_time(None) < 60)
    ):
        if datetime.timedelta(hours=8) < get_timedelta_now() < calc_sunset() and not storage.get(SKeys.evening):
            await ds.wc_1.on().run()
            device = ds.wc_1
        else:
            await ds.wc_2.on().run()
            device = ds.wc_2

        if ds.wc_1.in_quarantine() or ds.wc_2.in_quarantine():
            await run([ds.wc_1.on(), ds.wc_2.on()])

            device = None
            if not ds.wc_1.in_quarantine():
                device = ds.wc_1
            if not ds.wc_2.in_quarantine():
                device = ds.wc_2

        storage.put(SKeys.wc_lights, time.time())

        await asyncio.sleep(1)
        if device and not await device.is_on():
            await run([ds.wc_1.on(), ds.wc_2.on()])

        return 3 * MIN


@looper(1)
async def balcony_lights_on_actions():
    config = get_config()
    if config.pause:
        return 1 * MIN
    storage = Storage()
    ds = DeviceSet()

    if (
        not storage.get(SKeys.lights_locked)
        and not storage.get(SKeys.balcony_lock)
        and (
            get_timedelta_now() > calc_sunset(datetime.timedelta(minutes=10))
            or get_timedelta_now() < calc_sunrise()
            or storage.get(SKeys.evening)
        )
    ):
        balcony_sensor_motion_time = await ds.balcony_sensor.motion_time()
        if (
            not ds.balcony_sensor.in_quarantine()
            and not ds.balcony_lamp.in_quarantine()
            and balcony_sensor_motion_time < MIN
        ):
            await ds.balcony_lamp.on().run(
                lock_level=1,
                lock=datetime.timedelta(minutes=5) - datetime.timedelta(seconds=balcony_sensor_motion_time),
            )
            storage.put(SKeys.balcony_lights, time.time())
            return 5 * MIN


@looper(MIN)
async def lights_off_actions():
    config = get_config()
    if config.pause:
        return 1 * MIN
    storage = Storage()
    ds = DeviceSet()

    if not storage.get(SKeys.exit_lock):
        if (
            not storage.get(SKeys.night)
            and (
                await ds.exit_sensor.motion_time() > 3 * MIN
                and not ds.exit_sensor.in_quarantine()
                or ds.exit_sensor.in_quarantine()
                and time.time() - ds.exit_sensor.quarantine().timestamp > 7 * MIN
            )
            or storage.get(SKeys.night)
            and (
                await ds.wc_sensor.motion_time() > 7 * MIN
                and not ds.wc_sensor.in_quarantine()
                and await ds.exit_sensor.motion_time() > 7 * MIN
                and not ds.exit_sensor.in_quarantine()
                or ds.exit_sensor.in_quarantine()
                and time.time() - ds.exit_sensor.quarantine().timestamp > 7 * MIN
                and ds.wc_sensor.in_quarantine()
                and time.time() - ds.wc_sensor.quarantine().timestamp > 7 * MIN
            )
        ):
            await run([ds.lamp_e_1.off(), ds.lamp_e_2.off(), ds.lamp_e_3.off()])

    wc_term_humidity = await ds.wc_term.humidity()

    if (
        (not ds.exit_sensor.in_quarantine() or not ds.wc_sensor.in_quarantine())
        and not ds.air.in_quarantine()
        and not storage.get(SKeys.wc_lock)
        and 24 * HOUR > time.time() - storage.get(SKeys.wc_lights) > 2 * MIN
        and (await ds.wc_1.is_on() or await ds.wc_2.is_on())
        and await ds.exit_sensor.motion_time() > 3 * MIN
        and (
            ds.wc_sensor.in_quarantine()
            and await ds.exit_sensor.motion_time() > 10 * MIN
            or not ds.wc_sensor.in_quarantine()
            and await ds.wc_sensor.motion_time() > 7 * MIN
        )
        and not await ds.air.is_on()
        and (
            wc_term_humidity.quarantine
            and (
                not ds.exit_sensor.in_quarantine()
                and await ds.exit_sensor.motion_time() > 30 * MIN
                or not ds.wc_sensor.in_quarantine()
                and await ds.wc_sensor.motion_time() > 30 * MIN
            )
            or not wc_term_humidity.quarantine
            and wc_term_humidity.result < 65
        )
    ):
        await run([ds.wc_1.off(), ds.wc_2.off()])
        storage.put(SKeys.wc_lights, time.time() - 25 * HOUR)

    timedelta_now = get_timedelta_now()
    if (
        not storage.get(SKeys.lights_locked)
        and not storage.get(SKeys.balcony_lock)
        and not storage.get(SKeys.paint)
        and (
            timedelta_now > calc_sunset(datetime.timedelta(minutes=10))
            or timedelta_now < calc_sunrise()
            or storage.get(SKeys.evening)
        )
    ):
        if time.time() - storage.get(SKeys.balcony_lights) < 20 * MIN:
            balcony_sensor_motion_time = await ds.balcony_sensor.motion_time()
            balcony_sensor_2_motion_time = await ds.balcony_sensor_2.motion_time()
            balcony_sensor_state = (
                balcony_sensor_motion_time > 5 * MIN if not ds.balcony_sensor.in_quarantine() else None
            )
            balcony_sensor_2_state = (
                balcony_sensor_2_motion_time > 5 * MIN if not ds.balcony_sensor_2.in_quarantine() else None
            )
            balcony_sensor_state_long = (
                balcony_sensor_motion_time > 12 * MIN if not ds.balcony_sensor.in_quarantine() else None
            )
            balcony_sensor_2_state_long = (
                balcony_sensor_2_motion_time > 12 * MIN if not ds.balcony_sensor_2.in_quarantine() else None
            )
            if (
                balcony_sensor_state
                and balcony_sensor_2_state
                or balcony_sensor_state is None
                and balcony_sensor_2_state_long
                or balcony_sensor_2_state is None
                and balcony_sensor_state_long
                or balcony_sensor_state is None
                and balcony_sensor_2_state is None
                and time.time() - storage.get(SKeys.balcony_lights) > 12 * MIN
            ):
                if ds.balcony_lamp not in get_act(storage.get(SKeys.clicks)):
                    await ds.balcony_lamp.off().run()
