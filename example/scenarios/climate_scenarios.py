import datetime
import logging
import time

from example.configuration.config import get_config
from example.configuration.device_set import DeviceSet
from example.configuration.storage_keys import SKeys
from smarthouse.action_decorators import looper
from smarthouse.storage import Storage
from smarthouse.utils import HOUR, MIN
from smarthouse.yandex_client.client import YandexClient
from smarthouse.yandex_client.models import StateItem

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
    ya_client = YandexClient()
    ds = DeviceSet()

    water_level = await ds.humidifier_new.water_level()

    if water_level <= 10 and not storage.get(SKeys.water_notified):
        await storage.messages_queue.put({"message": "please insert water"})
        storage.put(SKeys.water_notified, True)

    if water_level >= 50 and storage.get(SKeys.water_notified):
        ya_client.locks_remove(ds.humidifier_new.device_id)
        ya_client.states_remove(ds.humidifier_new.device_id)
        storage.put(SKeys.water_notified, False)

    if water_level == 0:
        ya_client.locks_set(ds.humidifier_new.device_id, time.time() + 15 * 60, 3)
        if ya_client.states_in(ds.humidifier_new.device_id):
            cur_state = ya_client.states_get(ds.humidifier_new.device_id)
        else:
            cur_state = StateItem(actions_list=[])
        cur_state.checked = False
        ya_client.states_set(ds.humidifier_new.device_id, cur_state)
        return

    if water_level <= 10:
        return MIN


# todo: загрязнение дольше 2 часов


@looper(MIN)
async def bad_humidity_checker_scenario():
    config = get_config()
    if config.pause:
        return 1 * MIN
    storage = Storage()
    ds = DeviceSet()

    if storage.get(SKeys.lights_locked):
        return

    water_level = await ds.humidifier_new.water_level()

    humidifier_locked = storage.get(SKeys.humidifier_locked)

    if not humidifier_locked and water_level == 0:
        await ds.humidifier_new.on().run_async(
            check=False, feature_checkable=False, lock=datetime.timedelta(minutes=15), lock_level=3
        )
        storage.put(SKeys.humidifier_ond, time.time())

        storage.put(SKeys.humidifier_locked, True)

    if humidifier_locked and water_level != 0:
        storage.put(SKeys.humidifier_locked, False)

    if humidifier_locked:
        return

    balcony_door_open_time = await ds.balcony_door.open_time()
    balcony_door_closed = await ds.balcony_door.closed()

    air_cleaner_is_on = await ds.air_cleaner.is_on()
    humidifier_new_is_on = await ds.humidifier_new.is_on()

    checked_is_off = not humidifier_new_is_on

    humidifier_locked_door = storage.get(SKeys.humidifier_locked_door)

    humidifier_ond = storage.get(SKeys.humidifier_ond)
    humidifier_offed = storage.get(SKeys.humidifier_offed)

    last_command_is_on = humidifier_ond > humidifier_offed

    if (
        not humidifier_locked_door
        and not balcony_door_closed
        and 1 * MIN < balcony_door_open_time < 10 * MIN
        and not checked_is_off
        and last_command_is_on
    ):
        await ds.humidifier_new.off().run_async(check=False, feature_checkable=True)
        storage.put(SKeys.humidifier_offed, time.time())

        storage.put(SKeys.humidifier_locked_door, True)

    if humidifier_locked_door and (
        not balcony_door_closed
        and balcony_door_open_time > 10 * MIN
        or balcony_door_closed
        and balcony_door_open_time > 2 * MIN
    ):
        storage.put(SKeys.humidifier_locked_door, False)

    if humidifier_locked_door:
        return

    wc_term_humidity = await ds.wc_term.humidity()
    bed_air_sensor_humidity = await ds.bed_air_sensor.humidity()
    air_cleaner_humidity = await ds.air_cleaner.humidity()
    humidifier_new_humidity = await ds.humidifier_new.humidity()

    bed_air_sensor_trusted = not bed_air_sensor_humidity.quarantine
    wc_term_trusted = not wc_term_humidity.quarantine
    air_cleaner_trusted = not air_cleaner_humidity.quarantine and air_cleaner_is_on
    humidifier_new_trusted = not humidifier_new_humidity.quarantine

    wc_humidity = wc_term_humidity.result if wc_term_trusted else None
    room_humidity = (
        bed_air_sensor_humidity.result
        if bed_air_sensor_trusted
        else (
            humidifier_new_humidity.result
            if humidifier_new_trusted
            else (air_cleaner_humidity.result if air_cleaner_trusted else None)
        )
    )

    sleep = storage.get(SKeys.sleep)

    from_humidifier_ond = time.time() - humidifier_ond
    from_humidifier_offed = time.time() - humidifier_offed

    not_often = from_humidifier_ond > 10 * MIN and from_humidifier_offed > 10 * MIN

    long_on = last_command_is_on and from_humidifier_ond > HOUR
    long_off = not last_command_is_on and (
        from_humidifier_offed > 30 * MIN or sleep and from_humidifier_offed > 10 * MIN
    )

    if sleep:
        need_to_turn_on = room_humidity < 35 if room_humidity is not None else False
        need_to_turn_off = room_humidity >= 45 if room_humidity is not None else False
    else:
        need_to_turn_on = (room_humidity < 35 if room_humidity is not None else False) or (
            max(room_humidity, wc_humidity) < 40 if room_humidity is not None and wc_humidity is not None else False
        )
        need_to_turn_off = (room_humidity >= 45 if room_humidity is not None else False) or (
            max(room_humidity, wc_humidity) >= 55 if room_humidity is not None and wc_humidity is not None else False
        )

    if not_often or long_on or long_off:
        if need_to_turn_on and (checked_is_off or not last_command_is_on or long_on):
            await ds.humidifier_new.on().run_async()
            storage.put(SKeys.humidifier_ond, time.time())
        elif (need_to_turn_off or long_off) and not checked_is_off and (last_command_is_on or long_off):
            await ds.humidifier_new.off().run_async(check=long_off, feature_checkable=True)
            storage.put(SKeys.humidifier_offed, time.time())


@looper(15 * MIN)
async def air_cleaner_checker_scenario():
    config = get_config()
    if config.pause:
        return 1 * MIN
    ds = DeviceSet()

    if not await ds.air_cleaner.is_on():
        await ds.air_cleaner.on().run_async()
