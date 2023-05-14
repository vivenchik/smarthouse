import asyncio
import time

from home.action_decorators import looper
from home.device import RunQueuesSet, check_and_run, run
from home.logger import logger
from home.scenarios.storage_keys import SysSKeys
from home.storage import Storage
from home.telegram_client import TGClient
from home.utils import HOUR, MIN
from home.yandex_client.client import YandexClient


@looper(0.1)
async def worker_run():
    run_queue = RunQueuesSet().run

    task = await run_queue.get()
    await run(**task)

    run_queue.task_done()


@looper(0.1)
async def worker_check_and_run():
    run_queue = RunQueuesSet().check_and_run

    task = await run_queue.get()
    await check_and_run(**task)

    run_queue.task_done()


@looper(0.1)
async def notifications_ya_client():
    ya_client = YandexClient()
    tg_client = TGClient()

    message = await ya_client.messages_queue.get()
    await tg_client.write_tg(message)
    ya_client.messages_queue.task_done()


@looper(0.1)
async def notifications_storage():
    storage = Storage()
    tg_client = TGClient()

    message = await storage.messages_queue.get()
    await tg_client.write_tg(message)
    storage.messages_queue.task_done()


@looper(0.5)
async def tg_actions():
    tg_client = TGClient()
    await tg_client.update_tg()


@looper(0.1)
async def clear_tg():
    tg_client = TGClient()

    to_delete_timestamp, (to_delete_timestamp, message_id) = await tg_client.to_delete_messages.get()
    if to_delete_timestamp <= time.time():
        await tg_client.delete_message(int(message_id))
    else:
        await tg_client.to_delete_messages.put(
            (to_delete_timestamp, (to_delete_timestamp, message_id)),
        )
    tg_client.to_delete_messages.task_done()


@looper(10)
async def refresh_storage():
    storage = Storage()
    await storage.refresh()


@looper(5)
async def write_storage():
    storage = Storage()
    await storage._write_storage()


@looper(MIN)
async def ping_devices():
    ya_client = YandexClient()

    for device_id in ya_client._ping:
        await ya_client.device_info(device_id)
        await asyncio.sleep(1)


@looper(24 * HOUR)
async def stats():
    ya_client = YandexClient()
    logger.debug(f"{YandexClient._request.cache_info()}")

    for path, total_time in sorted(ya_client._stats.items(), key=lambda item: -item[1]):
        clean_path = path
        if path.startswith("/devices/"):
            clean_path = "/devices/" + ya_client.names.get(path[len("/devices/") :], path[len("/devices/") :])
        logger.debug(f"{clean_path}: {total_time}")
    ya_client._stats = {}


async def clear_retries():
    storage = Storage()
    await asyncio.sleep(10 * MIN)
    storage.put(SysSKeys.retries, 0)
