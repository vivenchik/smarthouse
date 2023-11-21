import logging
import time

from smarthouse.base_client.exceptions import InfraCheckError
from smarthouse.storage import Storage
from smarthouse.storage_keys import SysSKeys
from smarthouse.yandex_client.client import YandexClient
from smarthouse.yandex_client.models import StateItem

logger = logging.getLogger("root")


async def register_human(device_id: str, exc: InfraCheckError, state: StateItem, timestamp=None):
    if timestamp is None:
        timestamp = time.time()

    ya_client = YandexClient()

    time_ = ya_client._human_time_funcs.get(device_id, lambda timestamp=None: (timestamp or time.time()) + 15 * 60)(
        timestamp
    )

    if time_ < time.time():
        return

    storage = Storage()

    ya_client.locks_set(device_id, time_, level=10)
    ya_client.states_set(
        device_id,
        StateItem(actions_list=exc.wished_actions_list, excl=state.excl, checked=True, mutated=True),
    )
    storage.put(SysSKeys.last_human_detected, timestamp)
    logger.info(f"detected human:\n{exc}")
    await storage.messages_queue.put(
        {
            "message": f"Detected human:\n{exc}",
            "to_delete": True,
            "to_delete_timestamp": time_,
        }
    )
