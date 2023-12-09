import asyncio
import logging
import time

from smarthouse.action_decorators import looper
from smarthouse.storage import Storage
from smarthouse.storage_keys import SysSKeys
from smarthouse.telegram_client import TGClient
from smarthouse.utils import HOUR, MIN
from smarthouse.yandex_client.client import YandexClient
from smarthouse.yandex_client.device import RunQueuesSet, check_and_run, run
from smarthouse.yandex_client.models import DeviceCapabilityAction, StateItem
from smarthouse.yandex_client.utils import get_current_capabilities

logger = logging.getLogger("root")


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


@looper(3)
async def clear_tg():
    tg_client = TGClient()

    to_delete_timestamp, message_id = await tg_client.to_delete_messages.get()
    if 0 < to_delete_timestamp - time.time() < 5:
        return 0.1
    if to_delete_timestamp <= time.time():
        await tg_client.delete_message(int(message_id))
    else:
        await tg_client.to_delete_messages.put((to_delete_timestamp, message_id))
    tg_client.to_delete_messages.task_done()


@looper(10)
async def refresh_storage(s3_mode=False):
    if not s3_mode:
        storage = Storage()
        await storage.refresh()


@looper(5)
async def write_storage(s3_mode=False):
    storage = Storage()
    await storage._write_storage()

    if s3_mode:
        return MIN


@looper(15 * MIN)
async def update_iam_token():
    from smarthouse.yandex_cloud import YandexCloudClient

    cloud_client = YandexCloudClient()
    await cloud_client.update_iam_token()


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
        if total_time > 10:
            logger.debug(f"{clean_path}: {int(total_time)} secs")
    ya_client._stats = {}

    for device_id, calls_get in sorted(ya_client._calls_get.items(), key=lambda item: -item[1]):
        if calls_get > 5:
            logger.debug(f"GET {ya_client.names.get(device_id)}: {calls_get} times")
    ya_client._calls_get = {}

    for device_id, calls_post in sorted(ya_client._calls_post.items(), key=lambda item: -item[1]):
        if calls_post > 5:
            logger.debug(f"POST {ya_client.names.get(device_id)}: {calls_post} times")
    ya_client._calls_post = {}

    logger.debug(f"max_run_queue_size: {storage.get(SysSKeys.max_run_queue_size)}")
    logger.debug(f"max_check_and_run_queue_size: {storage.get(SysSKeys.max_check_and_run_queue_size)}")
    storage.put(SysSKeys.max_run_queue_size, 0)
    storage.put(SysSKeys.max_check_and_run_queue_size, 0)


async def clear_retries():
    storage = Storage()
    await asyncio.sleep(10 * MIN)
    storage.put(SysSKeys.retries, 0)
