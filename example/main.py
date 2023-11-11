import asyncio
import functools
import sys
import time

from example.configuration.config import get_config
from example.configuration.device_set import DeviceSet
from example.configuration.storage_keys import SKeys
from example.configuration.tg_handlers import get_commands, get_handlers
from example.configuration.web import routes
from example.scenarios.away_scenarios import away_actions_scenario
from example.scenarios.climate_scenarios import dry_actions_scenario, water_level_checker_scenario, wc_hydro_scenario
from example.scenarios.color_scenes_scenarios import (
    button_scenario,
    button_sleep_actions_scenario,
    random_colors_scenario,
)
from example.scenarios.dayly_lights_scenarios import (
    adaptive_lights_scenario,
    alarm_scenario,
    night_reset_scenario,
    scheduled_lights_scenario,
    scheduled_morning_lights_off_scenario,
    scheduled_morning_lights_scenario,
)
from example.scenarios.motion_light_scenarios import (
    balcony_lights_on_scenario,
    lights_corridor_on_scenario,
    lights_off_scenario,
    lights_wc_on_scenario,
)
from example.scenarios.utility_scenarios import not_prod_scenario, web_utils_scenario, worker_for_web_scenario
from smarthouse.app import App
from smarthouse.logger import logger
from smarthouse.scenarios.storage_keys import SysSKeys
from smarthouse.storage import Storage
from smarthouse.telegram_client import TGClient
from smarthouse.yandex_client.client import YandexClient


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
        ha_url=config.ha_url,
        ha_token=config.ha_token,
        tg_commands=get_commands(),
        tg_handlers=get_handlers(),
        prod=config.prod,
        aiohttp_routes=routes,
    )

    try:
        await app.prepare()

        storage = Storage()
        storage.put(SKeys.startup, time.time())

        ya_client = YandexClient()
        tg_client = TGClient()

        DeviceSet().init()
        ds = DeviceSet()

        lamp_groups = ds.lamp_groups
        tasks = [
            night_reset_scenario(),
            away_actions_scenario(),
            scheduled_morning_lights_scenario(),
            scheduled_morning_lights_off_scenario(),
            scheduled_lights_scenario(),
            wc_hydro_scenario(),
            lights_corridor_on_scenario(),
            lights_wc_on_scenario(),
            lights_off_scenario(),
            dry_actions_scenario(),
            web_utils_scenario(),
            button_scenario(),
            adaptive_lights_scenario(),
            # motion_lights_actions(),
            random_colors_scenario((lamp_groups[0],), (0, 10)),
            random_colors_scenario((lamp_groups[1],), (20, 30)),
            random_colors_scenario((lamp_groups[2],), (40, 50)),
            random_colors_scenario((lamp_groups[3],), (30, 50)),
            random_colors_scenario(lamp_groups, (60, 60), (60, 180), True),
            not_prod_scenario(),
            # reload_hub(),
            # refresh_storage(storage),
            alarm_scenario(),
            worker_for_web_scenario(),
            balcony_lights_on_scenario(),
            water_level_checker_scenario(),
            button_sleep_actions_scenario(),
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
            await asyncio.sleep(3600)
        sys.exit(1)

    finally:
        await ya_client.client.close()
        sys.exit(0)
