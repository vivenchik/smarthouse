import asyncio
import functools
import logging
import os
import signal
import time
from collections.abc import Coroutine
from typing import Awaitable, Iterable

import aiofiles
from aiohttp import web
from aiohttp.web_routedef import AbstractRouteDef

from smarthouse.scenarios.light_scenarios import (
    clear_retries,
    clear_tg,
    notifications_storage,
    notifications_ya_client,
    ping_devices,
    stats,
    tg_actions,
    update_iam_token,
    worker_check_and_run,
    worker_run,
    write_storage,
)
from smarthouse.scenarios.system_scenarios import clear_quarantine, detect_human
from smarthouse.storage import Storage
from smarthouse.storage_keys import SysSKeys
from smarthouse.telegram_client import TGClient
from smarthouse.yandex_client.client import YandexClient
from smarthouse.yandex_client.device import RunQueuesSet

logger = logging.getLogger("root")


def ignore_exc(func):
    @functools.wraps(func)
    async def wrapper():
        try:
            if isinstance(func, Coroutine):
                return await func
            else:
                return func()
        except Exception as exc:
            logger.exception(exc)

    return wrapper


class App:
    def __init__(
        self,
        storage_name: str | None,
        yandex_token: str = "",
        telegram_token: str | None = None,
        telegram_chat_id: str = "",
        ha_url: str = "",
        ha_token: str = "",
        service_account_id: str = "",
        key_id: str = "",
        private_key: str = "",
        aws_access_key_id: str = "",
        aws_secret_access_key: str = "",
        tg_commands: list[tuple[str, str]] | None = None,
        tg_handlers: list[tuple[str, Awaitable]] | None = None,
        prod: bool = False,
        s3_mode: bool = False,
        iam_mode: bool = False,
        aiohttp_routes: Iterable[AbstractRouteDef] | None = None,
    ):
        signal.signal(signal.SIGINT, self.exit_gracefully)
        signal.signal(signal.SIGTERM, self.exit_gracefully)

        self.storage_name = storage_name
        self.yandex_token = yandex_token
        self.telegram_token = telegram_token
        self.telegram_chat_id = telegram_chat_id
        self.ha_url = ha_url
        self.ha_token = ha_token
        self.service_account_id = service_account_id
        self.key_id = key_id
        self.private_key = private_key
        self.aws_access_key_id = aws_access_key_id
        self.aws_secret_access_key = aws_secret_access_key
        self.tg_commands = tg_commands
        self.tg_handlers = tg_handlers
        self.prod = prod
        self.s3_mode = s3_mode
        self.iam_mode = iam_mode

        self.tasks = (
            [
                notifications_storage(),
                notifications_ya_client(),
                tg_actions(),
                stats(),
                clear_retries(),
                ping_devices(),
                clear_tg(),
                write_storage(self.s3_mode),
                # refresh_storage(self.s3_mode),
                clear_quarantine(),
                detect_human(),
            ]
            + [worker_run()] * 100
            + [worker_check_and_run()] * 30
        )
        if self.iam_mode:
            self.tasks.append(update_iam_token())

        if aiohttp_routes is not None:
            app = web.Application()
            app.add_routes(aiohttp_routes)
            self.tasks.append(web._run_app(app))

    async def async_exit_gracefully(self):
        storage = Storage()
        ya_client = YandexClient()
        tg_client = TGClient()

        retries = storage.get(SysSKeys.retries, 0)
        storage.put(SysSKeys.retries, retries + 1)
        need_to_sleep = retries >= 5

        if need_to_sleep or os.path.getsize("./storage/main.log") > 500 * 1 << 20:
            storage.put(SysSKeys.clear_log, True)

        await ignore_exc(storage.write_shadow)()
        await ignore_exc(storage._write_storage(force=True))()

        while not storage.messages_queue.empty():
            message = await storage.messages_queue.get()
            await ignore_exc(tg_client.write_tg(message))()
            storage.messages_queue.task_done()

        while not ya_client.messages_queue.empty():
            message = await ya_client.messages_queue.get()
            await ignore_exc(tg_client.write_tg(message))()
            ya_client.messages_queue.task_done()

        await ya_client.client.close()

        if need_to_sleep:
            logger.info("going to sleep for an hour")
            ignore_exc(await tg_client.write_tg("going to sleep for an hour"))
            storage.put(SysSKeys.retries, 0)
            await asyncio.sleep(3600)

        logger.info("exited")
        await ignore_exc(tg_client.write_tg("exited"))()

    def exit_gracefully(self, signum, frame):
        signame = signal.Signals(signum).name
        logger.error(f"Signal handler called with signal {signame} ({signum})")

        loop = asyncio.get_running_loop()
        loop.run_until_complete(self.async_exit_gracefully())

    def add_tasks(self, tasks: list[Coroutine]):
        self.tasks.extend(tasks)

    async def prepare(self):
        if self.s3_mode or self.iam_mode:
            from smarthouse.yandex_cloud import YandexCloudClient

            await YandexCloudClient().init(
                service_account_id=self.service_account_id,
                key_id=self.key_id,
                private_key=self.private_key,
                aws_access_key_id=self.aws_access_key_id,
                aws_secret_access_key=self.aws_secret_access_key,
            )
        await Storage().init(storage_name=self.storage_name, s3_mode=self.s3_mode)

        YandexClient().init(yandex_token=self.yandex_token, prod=self.prod)

        # await HAClient().init(base_url=self.ha_url, ha_token=self.ha_token, prod=self.prod)

        TGClient().init(telegram_token=self.telegram_token, telegram_chat_id=self.telegram_chat_id, prod=self.prod)
        tg_client = TGClient()
        await tg_client._bot.set_my_commands(self.tg_commands)
        for pattern, func in self.tg_handlers:
            tg_client.register_handler(pattern, func)

        RunQueuesSet().init()

        storage = Storage()
        if storage.get(SysSKeys.clear_log):
            async with aiofiles.open("./storage/main.log", mode="w") as f:
                await f.write("")
            storage.put(SysSKeys.clear_log, False)

    async def run(self):
        storage = Storage()
        storage.put(SysSKeys.startup, time.time())

        tg_client = TGClient()

        logger.info("started")
        await storage.messages_queue.put({"message": "started"})

        try:
            return await asyncio.gather(*self.tasks)
        except BaseException as exc:
            logger.exception(exc)
            await ignore_exc(tg_client.write_tg(str(exc)))()
        finally:
            await self.async_exit_gracefully()
