import logging.config
import os

from example.configuration.config import get_config
from example.configuration.device_set import DeviceSet
from example.configuration.tg_handlers import get_commands, get_handlers
from example.configuration.web import routes
from example.scenarios.away_scenarios import away_actions_scenario
from example.scenarios.climate_scenarios import (
    air_cleaner_checker_scenario,
    bad_humidity_checker_scenario,
    water_level_checker_scenario,
    wc_hydro_scenario,
)
from example.scenarios.color_scenes_scenarios import (
    button_scenario,
    button_sleep_actions_scenario,
    div_modes_stats_scenario,
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
    lights_balcony_on_scenario,
    lights_corridor_on_scenario,
    lights_night_on_scenario,
    lights_off_scenario,
    lights_wc_on_scenario,
)
from example.scenarios.utility_scenarios import not_prod_scenario, worker_for_web_scenario
from smarthouse.app import App

CONF_FILE = f"{os.path.dirname(os.path.realpath(__file__))}/logger.conf"

logging.config.fileConfig(CONF_FILE)


logger = logging.getLogger("root")


async def main():
    config = get_config()

    app = App(
        storage_name=config.storage_name,
        yandex_token=config.yandex_token,
        telegram_token=config.telegram_token,
        telegram_chat_id=config.telegram_chat_id,
        ha_url=config.ha_url,
        ha_token=config.ha_token,
        service_account_id=config.service_account_id,
        key_id=config.key_id,
        private_key=config.private_key,
        aws_access_key_id=config.aws_access_key_id,
        aws_secret_access_key=config.aws_secret_access_key,
        tg_commands=get_commands(),
        tg_handlers=get_handlers(),
        prod=config.prod,
        s3_mode=config.s3_mode,
        iam_mode=config.iam_mode,
        aiohttp_routes=routes,
    )

    await app.prepare()

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
        lights_night_on_scenario(),
        lights_off_scenario(),
        button_scenario(),
        adaptive_lights_scenario(),
        random_colors_scenario((lamp_groups[0],), (0, 10)),
        random_colors_scenario((lamp_groups[1],), (20, 30)),
        random_colors_scenario((lamp_groups[2],), (40, 50)),
        random_colors_scenario((lamp_groups[3],), (30, 50)),
        random_colors_scenario(lamp_groups, (60, 60), (60, 180), True),
        not_prod_scenario(),
        # reload_hub_scenario(),
        alarm_scenario(),
        worker_for_web_scenario(),
        lights_balcony_on_scenario(),
        water_level_checker_scenario(),
        button_sleep_actions_scenario(),
        div_modes_stats_scenario(),
        bad_humidity_checker_scenario(),
        air_cleaner_checker_scenario(),
    ]
    app.add_tasks(tasks)

    await app.run()
