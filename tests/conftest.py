import asyncio
import copy
import json
import os
import uuid
from collections.abc import Callable
from unittest.mock import AsyncMock

import aiofiles
import pytest
import pytest_asyncio
from dotenv import load_dotenv
from pydantic import BaseModel

from example.configuration.device_set import DeviceSet
from home.base_client.models import LockItem
from home.device import RunQueuesSet
from home.storage import Storage
from home.yandex_client.client import YandexClient
from home.yandex_client.models import Action, Device, DeviceActionResponse, DeviceCapabilityAction, DeviceInfoResponse


def pytest_configure(config):
    load_dotenv()
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

    ACTIONS_LIST = [DeviceCapabilityAction(device_id=ITEM_UUID, capabilities=[("on_off", "on", True)])]

    return ITEM_UUID, DEVICE, ACTIONS_LIST


@pytest_asyncio.fixture
async def device_f():
    ITEM_UUID = str(uuid.uuid4())

    DEVICE = Device(
        id=ITEM_UUID,
        actions=[Action(type="devices.capabilities.on_off", state={"instance": "on", "value": False})],
    )

    ACTIONS_LIST = [DeviceCapabilityAction(device_id=ITEM_UUID, capabilities=[("on_off", "on", False)])]

    return ITEM_UUID, DEVICE, ACTIONS_LIST


lamp_response = None
action_response = None


async def get_lamp_response():
    global lamp_response
    if lamp_response is None:
        async with aiofiles.open(
            os.path.join(os.path.dirname(__file__), "mock_data/lamp_response.json"), mode="r"
        ) as f:
            lamp_response = json.loads(await f.read())
    return copy.deepcopy(lamp_response)


async def get_action_response():
    global action_response
    if action_response is None:
        async with aiofiles.open(
            os.path.join(os.path.dirname(__file__), "mock_data/action_response.json"), mode="r"
        ) as f:
            action_response = json.loads(await f.read())
    return copy.deepcopy(action_response)


@pytest.fixture(scope="function")
def base_client():
    from home.base_client.client import ActionRequestModelType, BaseClient, DeviceInfoResponseType

    class TestClient(BaseClient[DeviceInfoResponseType, ActionRequestModelType]):
        def __init__(self):
            super().__init__()
            self.base_init()

            self.call_count = 0

        def my_mock_method(self, device_id: str, mutation: Callable) -> None:
            self.call_count += 1

        async def _device_info(  # type: ignore[override]
            self, device_id: str, dont_log: bool = False, err_retry: bool = True, hash_seconds=1
        ) -> DeviceInfoResponse:
            return DeviceInfoResponse(**await get_lamp_response())

        async def _devices_action(self, ACTIONS_LIST: list[DeviceCapabilityAction]) -> DeviceActionResponse:
            return DeviceActionResponse(**await get_action_response())

        def device_from_action(self, action: DeviceCapabilityAction) -> BaseModel:
            return YandexClient().device_from_action(action)

    return TestClient()


@pytest.fixture(scope="function")
def ya_client():
    class TestClient(YandexClient):
        def __init__(self):
            super().__init__()
            self.base_init()

        async def _device_info(
            self, device_id: str, dont_log: bool = False, err_retry: bool = True, hash_seconds=1
        ) -> DeviceInfoResponse:
            return DeviceInfoResponse(**await get_lamp_response())

        async def _devices_action(self, ACTIONS_LIST: list[DeviceCapabilityAction]) -> DeviceActionResponse:
            return DeviceActionResponse(**await get_action_response())

        def device_from_action(self, action: DeviceCapabilityAction) -> BaseModel:
            return YandexClient().device_from_action(action)

    return TestClient()
