import asyncio
from collections.abc import Coroutine
from typing import Awaitable, Iterable

from aiohttp import web
from aiohttp.web_routedef import AbstractRouteDef

from smarthouse.logger import logger
from smarthouse.scenarios.light_scenarios import (
    clear_retries,
    clear_tg,
    notifications_storage,
    notifications_ya_client,
    ping_devices,
    stats,
    tg_actions,
    worker_check_and_run,
    worker_run,
    write_storage,
)
from smarthouse.scenarios.system_scenarios import clear_quarantine, detect_human
from smarthouse.storage import Storage
from smarthouse.telegram_client import TGClient
from smarthouse.yandex_client.client import YandexClient
from smarthouse.yandex_client.device import RunQueuesSet


class App:
    def __init__(
        self,
        storage_name: str | None,
        yandex_token: str = "",
        telegram_token: str | None = None,
        telegram_chat_id: str = "",
        ha_url: str = "",
        ha_token: str = "",
        tg_commands: list[tuple[str, str]] | None = None,
        tg_handlers: list[tuple[str, Awaitable]] | None = None,
        prod: bool = False,
        aiohttp_routes: Iterable[AbstractRouteDef] | None = None,
    ):
        self.storage_name = storage_name
        self.yandex_token = yandex_token
        self.telegram_token = telegram_token
        self.telegram_chat_id = telegram_chat_id
        self.ha_url = ha_url
        self.ha_token = ha_token
        self.tg_commands = tg_commands
        self.tg_handlers = tg_handlers
        self.prod = prod

        self.tasks = (
            [
                notifications_storage(),
                notifications_ya_client(),
                tg_actions(),
                stats(),
                clear_retries(),
                ping_devices(),
                clear_tg(),
                write_storage(),
                clear_quarantine(),
                detect_human(),
            ]
            + [worker_run()] * 10
            + [worker_check_and_run()] * 3
        )

        if aiohttp_routes is not None:
            app = web.Application()
            app.add_routes(aiohttp_routes)
            self.tasks.append(web._run_app(app))

    def add_tasks(self, tasks: list[Coroutine]):
        self.tasks.extend(tasks)

    async def prepare(self):
        await Storage().init(storage_name=self.storage_name)

        YandexClient().init(yandex_token=self.yandex_token, prod=self.prod)

        # await HAClient().init(base_url=self.ha_url, ha_token=self.ha_token, prod=self.prod)

        TGClient().init(telegram_token=self.telegram_token, telegram_chat_id=self.telegram_chat_id, prod=self.prod)
        tg_client = TGClient()
        await tg_client._bot.set_my_commands(self.tg_commands)
        for pattern, func in self.tg_handlers:
            tg_client.register_handler(pattern, func)

        RunQueuesSet().init()

    async def run(self):
        logger.info("started")
        await Storage().messages_queue.put({"message": "started"})

        return await asyncio.gather(*self.tasks)
