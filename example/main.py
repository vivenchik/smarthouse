import asyncio
import functools
import sys
import time

from example.configuration.config import get_config
from example.configuration.device_set import DeviceSet
from example.configuration.storage_keys import SKeys
from example.configuration.tg_handlers import get_commands, get_handlers
from example.configuration.web import routes
from example.scenarios.away_scenarios import away_actions
from example.scenarios.climate_scenarios import dry_actions, water_level_checker, wc_hydro_actions
from example.scenarios.color_scenes_scenarios import button_actions, button_sleep_actions, random_colors_actions
from example.scenarios.dayly_lights_scenarios import (
    adaptive_lights_actions,
    alarm,
    night_reset,
    scheduled_lights,
    scheduled_morning_lights,
    scheduled_morning_lights_off,
)
from example.scenarios.motion_light_scenarios import (
    balcony_lights_on_actions,
    lights_corridor_on_actions,
    lights_off_actions,
    lights_wc_on_actions,
)
from example.scenarios.utility_scenarios import not_prod, web_utils_actions, worker_for_web
from home.app import App
from home.logger import logger
from home.scenarios.storage_keys import SysSKeys
from home.scenarios.system_scenarios import clear_quarantine, detect_human
from home.storage import Storage
from home.telegram_client import TGClient
from home.yandex_client.client import YandexClient


def ignore_exc(func):
    @functools.wraps
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args)
        except Exception as exc:
            logger.exception(exc)

    return wrapper


async def main():
    config = get_config()

    app = App(
        storage_name=config.storage_name,
        yandex_token=config.yandex_token,
        telegram_token=config.telegram_token,
        telegram_chat_id=config.telegram_chat_id,
        tg_commands=get_commands(),
        tg_handlers=get_handlers(),
        prod=config.prod,
        aiohttp_routes=routes,
    )

    try:
        await app.prepare()

        storage = Storage()
        storage.put(SKeys.last_click, time.time())
        storage.put(SKeys.last_click_b_2, time.time())

        ya_client = YandexClient()
        tg_client = TGClient()

        DeviceSet().init()
        ds = DeviceSet()

        lamp_groups = ds.lamp_groups
        tasks = [
            night_reset(),
            away_actions(),
            scheduled_morning_lights(),
            scheduled_morning_lights_off(),
            scheduled_lights(),
            wc_hydro_actions(),
            lights_corridor_on_actions(),
            lights_wc_on_actions(),
            lights_off_actions(),
            dry_actions(),
            web_utils_actions(),
            button_actions(),
            adaptive_lights_actions(),
            # motion_lights_actions(),
            random_colors_actions((lamp_groups[0],), (0, 10)),
            random_colors_actions((lamp_groups[1],), (20, 30)),
            random_colors_actions((lamp_groups[2],), (40, 50)),
            random_colors_actions((lamp_groups[3],), (30, 50)),
            random_colors_actions(lamp_groups, (60, 60), (60, 180), True),
            not_prod(),
            clear_quarantine(),
            detect_human(),
            # reload_hub(),
            # refresh_storage(storage),
            alarm(),
            worker_for_web(),
            balcony_lights_on_actions(),
            water_level_checker(),
            button_sleep_actions(),
        ]
        app.add_tasks(tasks)

        await app.run()

    except Exception as exc:
        logger.exception(exc)
        logger.critical("its end")

        storage.put(SysSKeys.retries, storage.get(SysSKeys.retries, 0) + 1)

        await ignore_exc((storage._write_storage(force=True)))

        while not storage.messages_queue.empty():
            message = await storage.messages_queue.get()
            await ignore_exc(tg_client.write_tg(message))
            storage.messages_queue.task_done()

        while not ya_client.messages_queue.empty():
            message = await ya_client.messages_queue.get()
            await ignore_exc(tg_client.write_tg(message))
            ya_client.messages_queue.task_done()

        await ignore_exc(tg_client.write_tg("its end"))
        await ignore_exc(tg_client.write_tg(str(exc)))
        await ignore_exc(tg_client.write_tg_document("./main.log"))
        if storage.get(SysSKeys.retries, 0) >= 5:
            ignore_exc(await tg_client.write_tg("going to sleep an hour"))

        if storage.get(SysSKeys.retries, 0) >= 5:
            await asyncio.sleep(3600)
        sys.exit(1)

    finally:
        await ya_client.client.close()
        sys.exit(0)
