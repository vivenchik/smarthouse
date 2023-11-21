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
        and (wc_term_humidity.result > 60 and last_hydro > HOUR + 30 * MIN or wc_term_humidity.result > 75)
        and not await ds.air.is_on(10)
        and (
            await ds.wc_1.is_on()
            or await ds.wc_2.is_on()
            or wc_term_humidity.result > 75
            and last_hydro > HOUR + 30 * MIN
            and not storage.get(SKeys.sleep)
        )
    ):
        await ds.air.on().run_async()
        storage.put(SKeys.last_hydro, time.time())

    last_hydro = time.time() - storage.get(SKeys.last_hydro)
    if last_hydro < HOUR + 5 * MIN:
        exit_sensor = await ds.exit_sensor.motion_time(0.5)
        if last_hydro > exit_sensor and await ds.air.is_on(10):
            wc_term_humidity = await ds.wc_term.humidity()
            if not wc_term_humidity.quarantine and wc_term_humidity.result <= 55:
                await ds.air.off().run_async()
        elif HOUR < last_hydro < HOUR + 15:
            await ds.air.off().run_async()
            storage.put(SKeys.last_hydro, time.time() - (HOUR + 10 * MIN))


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

    water_level = await ds.humidifier_new.water_level()

    humidifier_locked = storage.get(SKeys.humidifier_locked)

    if not humidifier_locked and water_level == 0:
        await ds.humidifier_new.on().run_async(check=False)
        storage.put(SKeys.humidifier_ond, time.time())

        storage.put(SKeys.humidifier_locked, True)

    if humidifier_locked and water_level != 0:
        storage.put(SKeys.humidifier_locked, False)

    if humidifier_locked:
        return

    wc_term_humidity = await ds.wc_term.humidity()
    air_cleaner_humidity = await ds.air_cleaner.humidity()
    humidifier_new_humidity = await ds.humidifier_new.humidity()

    air_cleaner_is_on = await ds.air_cleaner.is_on()
    humidifier_new_is_on = await ds.humidifier_new.is_on()

    wc_term_trusted = not wc_term_humidity.quarantine
    air_cleaner_trusted = not air_cleaner_humidity.quarantine and air_cleaner_is_on
    humidifier_new_trusted = not humidifier_new_humidity.quarantine

    max_humidity = max(
        wc_term_humidity.result if wc_term_trusted else 0,
        air_cleaner_humidity.result if air_cleaner_trusted else 0,
        humidifier_new_humidity.result if humidifier_new_trusted else 0,
    )
    max_humidity_home = max(
        air_cleaner_humidity.result if air_cleaner_trusted else 0,
        humidifier_new_humidity.result if humidifier_new_trusted else 0,
    )

    sleep = storage.get(SKeys.sleep)

    checked_is_off = not humidifier_new_is_on

    humidifier_ond = storage.get(SKeys.humidifier_ond)
    humidifier_offed = storage.get(SKeys.humidifier_offed)

    last_command_is_on = humidifier_ond > humidifier_offed

    from_humidifier_ond = time.time() - humidifier_ond
    from_humidifier_offed = time.time() - humidifier_offed

    not_often = from_humidifier_ond > 30 * MIN and from_humidifier_offed > 30 * MIN

    long_on = last_command_is_on and from_humidifier_ond > HOUR
    long_off = not last_command_is_on and (
        from_humidifier_offed > 30 * MIN or sleep and from_humidifier_offed > 10 * MIN
    )

    need_to_turn_on = max_humidity < 35 or max_humidity_home < 30
    need_to_turn_off = max_humidity >= 55 or max_humidity_home >= 45 or long_off

    if not_often or long_on or long_off:
        if need_to_turn_on and (checked_is_off or not last_command_is_on or long_on):
            await ds.humidifier_new.on().run_async()
            storage.put(SKeys.humidifier_ond, time.time())
        elif need_to_turn_off and not checked_is_off and (last_command_is_on or long_off):
            await ds.humidifier_new.off().run_async(check=long_off, feature_checkable=True)
            storage.put(SKeys.humidifier_offed, time.time())


@looper(15 * MIN)
async def air_cleaner_checker_scenario():
    ds = DeviceSet()

    if not await ds.air_cleaner.is_on():
        await ds.air_cleaner.on().run_async()
