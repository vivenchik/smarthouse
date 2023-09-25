# SmartHouse
[![github](https://github.com/vivenchik/smarthouse/actions/workflows/main.yml/badge.svg)](https://github.com/vivenchik/smarthouse/actions)
[![Coverage Status](https://coveralls.io/repos/github/vivenchik/smarthouse/badge.svg?branch=master)](https://coveralls.io/github/vivenchik/smarthouse?branch=master)
[![Checked with mypy](https://www.mypy-lang.org/static/mypy_badge.svg)](https://mypy-lang.org/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Documentation Status](https://readthedocs.org/projects/smarthouselib/badge/?version=latest)](https://smarthouselib.readthedocs.io/en/latest/?badge=latest)

SmartHouse - библиотека для управления умным домом. На текущий момент реализована интеграция с экосистемой [Яндекса](https://yandex.ru/dev/dialogs/smart-home/doc/concepts/platform-protocol.html).

Какие задачи решает
-------------
* Каркас для написания сценариев
* Использование устройств как объектов или напрямую через клиента
* Доведение устройств до конечного состояния (проверяет с сервера)
* Введение устройств в карантин, если они не отвечают или как-то еще сломаны, таким образом, чтобы сценарии продолжали работать корректно
* При быстром выводе из карантина (происходит опрос устройства) после последней команды доведет устройство до состояния с последней команды
* Хранение последних данных с устройств
* Система lock'ов устройств
* Обнаружение человеческого вмешательства и установка lock'ов, от сценариев на настроенное время
* Легкое хранилище данных в файле
* Интеграция с web для управления
* Интеграция с tg ботом для сообщений об ошибках и управлением

Quick start
-----------
SmartHouse can be installed using pip:

```bash
pip install smarthouse
```

Usage example:

```python
import asyncio
import datetime
import time

from aiohttp import web

from smarthouse.action_decorators import looper, scheduler
from smarthouse.app import App
from smarthouse.yandex_client.device import HSVLamp, LuxSensor, run_async
from smarthouse.storage import Storage
from smarthouse.telegram_client import TGClient


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
        state_lux = await lux_sensor.illumination(proceeded_last=True)

    needed_b = 1 - min(state_lux.result, 200) / 200

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
```
