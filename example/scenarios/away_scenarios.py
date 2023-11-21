import asyncio
import logging
import time

from example.configuration.config import get_config
from example.configuration.device_set import DeviceSet
from example.configuration.storage_keys import SKeys
from example.scenarios.light_utils import calc_sunset
from example.scenarios.utils import turn_off_all, turn_on_act
from smarthouse.action_decorators import looper
from smarthouse.storage import Storage
from smarthouse.utils import HOUR, MIN, get_time, get_timedelta_now
from smarthouse.yandex_client.client import YandexClient

logger = logging.getLogger("root")


@looper(5)
async def away_actions_scenario():
    config = get_config()
    if config.pause:
        return 1 * MIN
    ya_client = YandexClient()
    storage = Storage()
    ds = DeviceSet()

    door = await ds.exit_door.open_time()
    hash_seconds = MIN if door > 20 * MIN else 0.5
    exit_sensor = await ds.exit_sensor.motion_time(hash_seconds)
    room_sensor = await ds.room_sensor.motion_time(hash_seconds)
    wc_sensor = await ds.wc_sensor.motion_time(hash_seconds)

    after_last_click = time.time() - storage.get(SKeys.last_click)
    after_last_click_b_2 = time.time() - storage.get(SKeys.last_click_b_2)
    after_last_human_detected = time.time() - storage.get(SKeys.last_human_detected)

    after_last_cleanup = time.time() - storage.get(SKeys.last_cleanup)
    after_last_notify = time.time() - storage.get(SKeys.last_notify)
    after_last_silence = time.time() - storage.get(SKeys.last_silence)
    after_last_on = time.time() - storage.get(SKeys.last_on)
    after_last_quieting = time.time() - storage.get(SKeys.last_quieting)

    delta = door - min(
        exit_sensor, room_sensor, wc_sensor, after_last_click, after_last_click_b_2, after_last_human_detected
    )

    sensors = {config.exit_sensor_id, config.room_sensor_id, config.wc_sensor_id}
    if len(sensors & ya_client.quarantine_ids()) == len(sensors) or ds.exit_door.in_quarantine():
        delta = 100

    state_i_am_away = (
        door > 3 * MIN and (delta < 0 or 5 * MIN < after_last_cleanup < 18 * MIN) and not storage.get(SKeys.sleep)
    )

    if 5 * 24 * HOUR < after_last_cleanup:
        await storage.messages_queue.put({"message": "go away"})
        storage.put(SKeys.last_cleanup, time.time() - 10 * HOUR)

    if state_i_am_away:
        if 4 * MIN < door < after_last_notify and 8 * HOUR < after_last_cleanup:
            logger.info("notifying")
            await ya_client.run_scenario(config.alert_scenario_id)
            storage.put(SKeys.last_notify, time.time())

        if 5 * MIN < door and 8 * HOUR < after_last_cleanup:
            logger.info(f"turning on cleaner {int(delta)}")
            await ds.cleaner.on().run_async()
            storage.put(SKeys.last_cleanup, time.time())
            storage.put(SKeys.cleanups, storage.get(SKeys.cleanups, 0) + 1)

        if 18 * MIN < door < after_last_notify:
            logger.info("notifying")
            await ya_client.run_scenario(config.alert_scenario_id)
            storage.put(SKeys.last_notify, time.time())

        if 20 * MIN < door < after_last_silence:
            logger.info("turning off lights and music")
            storage.put(SKeys.lights_locked, True)
            await ya_client.run_scenario(config.silence_scenario_id)
            await asyncio.sleep(5)
            await turn_off_all()
            await ds.air.off().run_async()
            storage.put(SKeys.last_silence, time.time())
            await asyncio.sleep(5)
            await ya_client.run_scenario(config.bluetooth_off_scenario_id)

            water_level = await ds.humidifier_new.water_level()
            humidifier_new_is_on = await ds.humidifier_new.is_on(MIN)
            checked_is_off = not humidifier_new_is_on
            humidifier_ond = storage.get(SKeys.humidifier_ond)
            humidifier_offed = storage.get(SKeys.humidifier_offed)
            last_command_is_on = humidifier_ond > humidifier_offed
            from_humidifier_offed = time.time() - humidifier_offed

            long_off = not last_command_is_on and from_humidifier_offed > 90 * MIN

            if not checked_is_off and water_level > 0 and (last_command_is_on or long_off):
                logger.info("turning off humidifier")
                await ds.humidifier_new.off().run_async(check=long_off, feature_checkable=True)
                storage.put(SKeys.humidifier_offed, time.time())

            if after_last_cleanup < 30 * MIN:
                cleaner_battery_level = await ds.cleaner.battery_level()
                if not 50 < cleaner_battery_level < 95:  # because we cant check on_off state
                    logger.info(f"strange cleaner battery_level {cleaner_battery_level}")
                    await storage.messages_queue.put({"message": "looks like cleaner is offed"})
                    storage.put(SKeys.last_cleanup, time.time() - 10 * HOUR)

        if 2 * HOUR < door < 2 * HOUR + 10 * MIN and await ds.humidifier_new.is_on(MIN):
            await ds.humidifier_new.off().run_async()

    else:
        if door < 10 * MIN:
            if after_last_cleanup < 10 * MIN:
                logger.info("turning off cleaner")
                await ds.cleaner.off().run_async()
                storage.put(SKeys.last_cleanup, time.time() - 10 * HOUR)
                storage.put(SKeys.cleanups, max(storage.get(SKeys.cleanups, 0) - 1, 0))
            elif after_last_cleanup < 30 * MIN and after_last_quieting > after_last_cleanup:
                logger.info("quieting cleaner")
                await ds.cleaner.change_work_speed("quiet").run_async()
                storage.put(SKeys.last_quieting, time.time())

            if after_last_silence < after_last_on:
                logger.info("welcome home")
                storage.put(SKeys.lights_locked, False)

                after_sunset = get_timedelta_now() >= calc_sunset()
                if after_sunset or get_time().hour < 6 or storage.get(SKeys.evening):
                    logger.info("turning on lights (welcome)")
                    await turn_on_act(storage.get(SKeys.clicks), storage.get(SKeys.clicks))
                    if after_sunset:
                        await ya_client.run_scenario(config.music_scenario_id)

                water_level = await ds.humidifier_new.water_level()

                logger.info("turning on humidifier")
                await ds.humidifier_new.on().run_async(check=water_level > 0)
                storage.put(SKeys.humidifier_ond, time.time())

                if storage.get(SKeys.cleanups, 0) >= 6:
                    await storage.messages_queue.put({"message": "insert water in cleaner /water_done"})

                storage.put(SKeys.last_on, time.time())

        if after_last_notify < MIN:
            await ya_client.run_scenario(config.ok_scenario_id)
            storage.put(SKeys.last_notify, time.time() - 2 * MIN)

    if state_i_am_away or after_last_cleanup < 30 * MIN or storage.get(SKeys.lights_locked) or door < 5 * MIN:
        return 1
    else:
        return 2 * MIN
