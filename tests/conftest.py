import asyncio
import uuid
from unittest.mock import AsyncMock

import pytest_asyncio

from src.example.configuration.device_set import DeviceSet
from src.lib.base_client.models import LockItem
from src.lib.device import RunQueuesSet
from src.lib.storage import Storage
from src.lib.yandex_client.client import YandexClient
from src.lib.yandex_client.models import Action, Device, DeviceCapabilityAction


def pytest_configure(config):
    YandexClient().init(prod=True)
    RunQueuesSet().init()
    DeviceSet().init()
    asyncio.run(Storage().init(storage_name=None))


@pytest_asyncio.fixture
async def ya_client_mock():
    mock = AsyncMock(spec=YandexClient)
    mock._quarantine = {}
    mock.quarantine_ids.return_value = set()
    mock.quarantine_in.return_value = False
    mock.states = {}
    mock._locks = {}

    def locks_set(device_id: str, timestamp: float, level: int = 0) -> None:
        mock._locks[device_id] = LockItem(level=level, timestamp=timestamp)

    mock.locks_set = locks_set
    mock.run_scenario.return_value = None
    mock._check_devices_capabilities.return_value = None
    return mock


@pytest_asyncio.fixture
async def device():
    ITEM_UUID = str(uuid.uuid4())

    DEVICE = Device(
        id=ITEM_UUID,
        actions=[Action(type="devices.capabilities.on_off", state={"instance": "on", "value": True})],
    )

    ACTIONS_list = [DeviceCapabilityAction(device_id=ITEM_UUID, capabilities=[("on_off", "on", True)])]

    return ITEM_UUID, DEVICE, ACTIONS_list


@pytest_asyncio.fixture
async def device_f():
    ITEM_UUID = str(uuid.uuid4())

    DEVICE = Device(
        id=ITEM_UUID,
        actions=[Action(type="devices.capabilities.on_off", state={"instance": "on", "value": False})],
    )

    ACTIONS_list = [DeviceCapabilityAction(device_id=ITEM_UUID, capabilities=[("on_off", "on", False)])]

    return ITEM_UUID, DEVICE, ACTIONS_list
