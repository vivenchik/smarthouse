import asyncio
import copy
import logging
import time

from smarthouse.action_decorators import looper
from smarthouse.base_client.exceptions import DeviceOffline, InfraCheckError
from smarthouse.scenarios.storage_keys import SysSKeys
from smarthouse.scenarios.utils import register_human
from smarthouse.storage import Storage
from smarthouse.utils import MIN
from smarthouse.yandex_client.client import YandexClient
from smarthouse.yandex_client.models import DeviceCapabilityAction, StateItem
from smarthouse.yandex_client.utils import get_current_capabilities

logger = logging.getLogger("root")


@looper(10)
async def clear_quarantine():
    ya_client = YandexClient()
    storage = Storage()
    quarantine_notifications = storage.get(SysSKeys.quarantine_notifications, {})
    quarantine_keys = ya_client.quarantine_ids()
    for device_id in quarantine_keys:
        if device_id in ya_client._ping and (info := ya_client.quarantine_get(device_id)) is not None:
            if (device_info := await ya_client.device_info(device_id, True)) is not None:
                quarantine_notifications[device_id] = 0
                ya_client._quarantine_remove(device_id)
                if info.data is not None and time.time() - info.timestamp < 10 * MIN:
                    await ya_client.change_devices_capabilities(info.data["actions"])
                elif ya_client.states_in(device_id):
                    state = ya_client.states_get(device_id)
                    try:
                        await ya_client._check_devices_capabilities(
                            state.actions_list, {device_id: state.excl}, err_retry=False, real_action=False
                        )
                    except DeviceOffline:
                        ya_client._quarantine_set(device_id)
                    except InfraCheckError as exc:
                        await register_human(device_id, exc, state, info.timestamp)
                else:
                    ya_client.states_set(
                        device_id,
                        StateItem(
                            actions_list=[
                                DeviceCapabilityAction(
                                    device_id=device_id, capabilities=get_current_capabilities(device_info)
                                )
                            ],
                            excl=(),
                            checked=True,
                            mutated=True,
                        ),
                    )
            elif time.time() - info.timestamp > 3600 * (2 ** quarantine_notifications.get(device_id, 0)):
                await storage.messages_queue.put(
                    {
                        "message": f"{ya_client.names.get(device_id, device_id)}: "
                        f"{int(time.time() - info.timestamp) // 3600}h",
                        "to_delete": True,
                        "to_delete_timestamp": time.time() + 10 * MIN,
                    }
                )
                quarantine_notifications[device_id] = quarantine_notifications.get(device_id, 0) + 1

    storage.put(SysSKeys.quarantine_notifications, quarantine_notifications)


@looper(10)
async def detect_human():
    ya_client = YandexClient()

    states_keys = copy.deepcopy(list(ya_client.states_keys()))
    for device_id in states_keys:
        if ya_client.states_in(device_id):
            state = ya_client.states_get(device_id)
            if state is not None and state.checked and not ya_client.quarantine_in(device_id):
                try:
                    await ya_client._check_devices_capabilities(
                        state.actions_list, {device_id: state.excl}, err_retry=False, real_action=False
                    )
                except DeviceOffline:
                    continue
                except InfraCheckError:
                    await asyncio.sleep(12)

                    if ya_client.states_in(device_id):
                        state2 = ya_client.states_get(device_id)
                        if state != state2:
                            continue

                        try:
                            await ya_client._check_devices_capabilities(
                                state.actions_list, {device_id: state.excl}, err_retry=False, real_action=False
                            )
                        except DeviceOffline:
                            continue
                        except InfraCheckError as exc:
                            await register_human(device_id, exc, state, time.time())
