import asyncio
import time

from smarthouse.action_decorators import looper
from smarthouse.logger import logger
from smarthouse.scenarios.storage_keys import SysSKeys
from smarthouse.storage import Storage
from smarthouse.telegram_client import TGClient
from smarthouse.utils import HOUR, MIN
from smarthouse.yandex_client.client import YandexClient
from smarthouse.yandex_client.device import RunQueuesSet, check_and_run, run
from smarthouse.yandex_client.models import DeviceCapabilityAction, StateItem
from smarthouse.yandex_client.utils import get_current_capabilities


async def worker_run():
    while True:
        try:
            run_queue = RunQueuesSet().run

            task = await run_queue.get()
            await run(**task)

            run_queue.task_done()
        except Exception:
            pass


async def worker_check_and_run():
    while True:
        try:
            run_queue = RunQueuesSet().check_and_run

            task = await run_queue.get()
            await check_and_run(**task)

            run_queue.task_done()
        except Exception:
            pass


@looper(0)
async def notifications_ya_client():
    ya_client = YandexClient()
    tg_client = TGClient()

    message = await ya_client.messages_queue.get()
    await tg_client.write_tg(**message)
    ya_client.messages_queue.task_done()


@looper(0)
async def notifications_storage():
    storage = Storage()
    tg_client = TGClient()

    message = await storage.messages_queue.get()
    await tg_client.write_tg(**message)
    storage.messages_queue.task_done()


@looper(0.5)
async def tg_actions():
    tg_client = TGClient()
    await tg_client.update_tg()


@looper(0.1)
async def clear_tg():
    tg_client = TGClient()

    to_delete_timestamp, message_id = await tg_client.to_delete_messages.get()
    if to_delete_timestamp <= time.time():
        await tg_client.delete_message(int(message_id))
    else:
        await tg_client.to_delete_messages.put((to_delete_timestamp, message_id))
    tg_client.to_delete_messages.task_done()


@looper(10)
async def refresh_storage():
    return
    storage = Storage()
    await storage.refresh()


@looper(MIN)
async def write_storage():
    storage = Storage()
    await storage._write_storage()


@looper(MIN)
async def ping_devices():
    ya_client = YandexClient()

    for device_id in ya_client._ping:
        device_info = await ya_client.device_info(device_id)

        if not ya_client.quarantine_in(device_id) and not ya_client.states_in(device_id):
            ya_client.states_set(
                device_id,
                StateItem(
                    actions_list=[
                        DeviceCapabilityAction(device_id=device_id, capabilities=get_current_capabilities(device_info))
                    ],
                    excl=(),
                    checked=True,
                    mutated=True,
                ),
            )

        await asyncio.sleep(1)


@looper(24 * HOUR)
async def stats():
    ya_client = YandexClient()
    storage = Storage()
    logger.debug(f"{YandexClient._request.cache_info()}")

    for path, total_time in sorted(ya_client._stats.items(), key=lambda item: -item[1]):
        clean_path = path
        if path.startswith("/devices/"):
            clean_path = "/devices/" + ya_client.names.get(path[len("/devices/") :], path[len("/devices/") :])
        logger.debug(f"{clean_path}: {total_time}")
    ya_client._stats = {}

    logger.debug(f"max_run_queue_size: {storage.get(SysSKeys.max_run_queue_size)}")
    logger.debug(f"max_check_and_run_queue_size: {storage.get(SysSKeys.max_check_and_run_queue_size)}")
    storage.put(SysSKeys.max_run_queue_size, 0)
    storage.put(SysSKeys.max_check_and_run_queue_size, 0)


async def clear_retries():
    storage = Storage()
    await asyncio.sleep(10 * MIN)
    storage.put(SysSKeys.retries, 0)
