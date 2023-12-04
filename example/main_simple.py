import asyncio
import datetime
import time

from aiohttp import web

from smarthouse.action_decorators import looper, scheduler
from smarthouse.app import App
from smarthouse.storage import Storage
from smarthouse.telegram_client import TGClient
from smarthouse.yandex_client.device import HSVLamp, LuxSensor, run_async


def calc_sunset():
    return datetime.timedelta(hours=18)


@scheduler((calc_sunset,))
async def pause_reset():
    storage = Storage()
    storage.put("pause", False)


@looper(3, (datetime.timedelta(hours=10), calc_sunset))
async def adaptive_lights_actions(lux_sensor, lamp_g_1, lamp_g_2):
    storage = Storage()

    if storage.get("pause"):
        return

    state_lux = await lux_sensor.illumination()
    if lux_sensor.in_quarantine() and lux_sensor.quarantine().timestamp + 5 * 60 > time.time():
        state_lux = await lux_sensor.illumination(process_last=True)

    needed_b = int((1 - min(state_lux.result, 200) / 200) * 100)

    await run_async([lamp.on_temp(4500, needed_b) for lamp in (lamp_g_1, lamp_g_2)])


async def tg_pause_handler(tg_client: TGClient, update):
    storage = Storage()
    storage.put("pause", True)
    await tg_client.write_tg("done")


routes = web.RouteTableDef()


async def main():
    app = App(
        storage_name="./storage/storage.yaml",
        yandex_token="YA Token",
        telegram_token="TG Token",
        telegram_chat_id="Tg chat id",
        tg_commands=[
            ("pause", "Pause"),
        ],
        tg_handlers=[
            (r"/pause", tg_pause_handler),
        ],
        prod=True,
        aiohttp_routes=routes,
    )

    await app.prepare()
    lux_sensor = LuxSensor("3d580790-00dc-4ce3-9892-a4cdbb346269", "Датчик освещенности")
    lamp_g_1 = HSVLamp("4b950171-0df0-4b23-aaeb-0f21c7393e73", "Лампа гостиная 1")
    lamp_g_2 = HSVLamp(
        "ed7f9d93-c79e-44b9-985d-0f252a26c894", "Лампа гостиная 2", human_time_func=lambda: time.time() + 15 * 60
    )
    tasks = [
        adaptive_lights_actions(lux_sensor, lamp_g_1, lamp_g_2),
        pause_reset(),
    ]
    app.add_tasks(tasks)

    await app.run()


if __name__ == "__main__":
    asyncio.run(main())
