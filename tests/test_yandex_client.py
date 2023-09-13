import datetime
from unittest import mock

import aiohttp
import pytest

from smarthouse.base_client.exceptions import InfraCheckError
from smarthouse.yandex_client.client import YandexClient
from smarthouse.yandex_client.models import Action, Device, DeviceCapabilityAction, StateItem
from tests.conftest import get_action_response, get_lamp_response


@pytest.mark.asyncio
async def test_register_device(base_client):
    device_id = "test_device"
    name = "Test Device"

    base_client.register_device(device_id=device_id, name=name)

    assert device_id in base_client.names
    assert name == base_client.names[device_id]
    assert device_id in base_client._human_time_funcs


@pytest.mark.asyncio
async def test_register_mutation(base_client):
    device_id = "test_device"

    assert device_id not in base_client._mutations
    assert base_client.call_count == 0

    base_client.register_mutation(device_id=device_id, mutation=base_client.my_mock_method)

    assert base_client.call_count == 0
    assert device_id in base_client._mutations
    assert base_client._mutations[device_id] == base_client.my_mock_method


@pytest.mark.asyncio
async def test_quarantine_methods(base_client):
    device_id = "test_device"
    data = {"key": "value"}

    # Проверяем начальное состояние карантина
    assert not base_client.quarantine_in(device_id)
    assert base_client.quarantine_get(device_id) is None
    assert device_id not in base_client.quarantine_ids()

    # Проверяем, что метод _quarantine_set работает корректно
    base_client._quarantine_set(device_id=device_id, data=data)
    assert base_client.quarantine_in(device_id)
    assert base_client.quarantine_get(device_id).data == data
    assert device_id in base_client.quarantine_ids()

    # Проверяем, что метод _quarantine_remove работает корректно
    base_client._quarantine_remove(device_id=device_id)
    assert not base_client.quarantine_in(device_id)
    assert base_client.quarantine_get(device_id) is None
    assert device_id not in base_client.quarantine_ids()


@pytest.mark.asyncio
async def test_locks_methods(base_client):
    device_id_1 = "device_1"
    device_id_2 = "device_2"
    timestamp_1 = 123456.0
    timestamp_2 = 789012.0

    # Проверяем начальное состояние блокировки
    assert not base_client.locks_in(device_id_1)
    assert not base_client.locks_in(device_id_2)

    # Проверяем метод locks_set
    base_client.locks_set(device_id=device_id_1, timestamp=timestamp_1, level=2)
    assert base_client.locks_in(device_id_1)
    assert not base_client.locks_in(device_id_2)
    assert base_client.locks_get(device_id=device_id_1).level == 2
    assert base_client.locks_get(device_id=device_id_1).timestamp == timestamp_1

    # Проверяем метод locks_reset
    base_client.locks_set(device_id=device_id_2, timestamp=timestamp_2, level=1)
    assert base_client.locks_in(device_id_1)
    assert base_client.locks_in(device_id_2)
    base_client.locks_reset()
    assert not base_client.locks_in(device_id_1)
    assert not base_client.locks_in(device_id_2)


@pytest.mark.asyncio
async def test_ask_permissions(base_client):
    device_id = "test_device"

    assert not base_client.states_in(device_id)

    result = await base_client.ask_permissions([(device_id, None)])
    assert result == [device_id]

    base_client.locks_set(device_id=device_id, timestamp=123456.0, level=2)

    result = await base_client.ask_permissions([(device_id, None)])
    assert result == [device_id]

    base_client.locks_set(device_id=device_id, timestamp=1234560000000000000000.0, level=2)

    result = await base_client.ask_permissions([(device_id, None)])
    assert result == []

    result = await base_client.ask_permissions([(device_id, None)], lock_level=3, lock=100)
    assert result == [device_id]


@pytest.mark.asyncio
async def test_devices_action(ya_client, device):
    ITEM_UUID, DEVICE, ACTIONS_LIST = device

    # Регистрация мутации
    ya_client.register_mutation(ITEM_UUID, lambda state: state)

    result = await ya_client.devices_action(ACTIONS_LIST)
    result = await ya_client._check_devices_capabilities(ACTIONS_LIST)

    assert result is None


@pytest.mark.asyncio
async def test_device_info(base_client):
    device_id = "test_device"

    assert not base_client.last_in(device_id)

    result = await base_client.device_info(device_id=device_id)
    assert result is not None

    result = await base_client.device_info(device_id=device_id, proceeded_last=True)
    assert result is not None


class MockResponse:
    def __init__(self, _json, status):
        self._json = _json
        self.status = status
        self.content_type = "application/json"

    async def json(self):
        return self._json

    async def text(self):
        return str(self._json)

    def raise_for_status(self):
        if self.status != 200:
            raise aiohttp.ClientResponseError(mock.Mock(), mock.Mock(), status=self.status)

    async def __aexit__(self, exc_type, exc, tb):
        pass

    async def __aenter__(self):
        return self


@pytest.mark.asyncio
async def test_quarantine_yandex_error(mocker, device):
    ITEM_UUID, DEVICE, ACTIONS_LIST = device
    ya_client = YandexClient()
    resp = MockResponse({}, 500)
    mocker.patch("aiohttp.ClientSession.request", return_value=resp)

    await ya_client.check_capability(ITEM_UUID, "on_off")
    assert ya_client.quarantine_in(ITEM_UUID)


@pytest.mark.asyncio
async def test_retry(mocker, device):
    ITEM_UUID, DEVICE, ACTIONS_LIST = device
    ya_client = YandexClient()
    lamp_response = await get_lamp_response()
    lamp_response["state"] = "offline"
    lamp_response["id"] = ITEM_UUID
    resp_offline = MockResponse(lamp_response, 200)

    lamp_response_online = await get_lamp_response()
    lamp_response_online["id"] = ITEM_UUID
    resp = MockResponse(lamp_response_online, 200)
    # mocker.patch("asyncio.sleep", new_callable=AsyncMock)
    with mocker.patch("aiohttp.ClientSession.request", side_effect=[resp_offline, resp]):
        await ya_client.check_capability(ITEM_UUID, "on_off")
    assert not ya_client.quarantine_in(ITEM_UUID)


@pytest.mark.asyncio
async def test_quarantine_get(mocker, device):
    ITEM_UUID, DEVICE, ACTIONS_LIST = device
    ya_client = YandexClient()
    lamp_response = await get_lamp_response()
    lamp_response["state"] = "offline"
    lamp_response["id"] = ITEM_UUID
    resp = MockResponse(lamp_response, 200)
    mocker.patch("aiohttp.ClientSession.request", return_value=resp)

    await ya_client.check_capability(ITEM_UUID, "on_off")
    assert ya_client.quarantine_in(ITEM_UUID)
    ITEM_UUID_2 = "22c4455b-ce9b-49d8-ab0e-ec0468a5f7a6"
    await ya_client.check_capability(ITEM_UUID_2, "on_off")
    assert ya_client.quarantine_in(ITEM_UUID_2)
    assert ya_client.quarantine_get(ITEM_UUID).timestamp < ya_client.quarantine_get(ITEM_UUID_2).timestamp


@pytest.mark.asyncio
async def test_quarantine_action(mocker, device):
    ITEM_UUID, DEVICE, ACTIONS_LIST = device
    ya_client = YandexClient()
    action_response = await get_action_response()
    action_response["devices"][0]["capabilities"][0]["state"]["action_result"]["status"] = "FAIL"
    action_response["devices"][0]["id"] = ITEM_UUID
    resp = MockResponse(action_response, 200)
    mocker.patch("aiohttp.ClientSession.request", return_value=resp)

    await ya_client.change_devices_capabilities(
        [DeviceCapabilityAction(device_id=ITEM_UUID, capabilities=[("on_off", "on", True)])]
    )
    assert ya_client.quarantine_in(ITEM_UUID)
    assert ya_client.quarantine_get(ITEM_UUID).data == {
        "actions": [DeviceCapabilityAction(device_id=ITEM_UUID, capabilities=[("on_off", "on", True)])]
    }

    await ya_client.change_devices_capabilities(
        [DeviceCapabilityAction(device_id=ITEM_UUID, capabilities=[("on_off", "on", False)])]
    )

    lamp_response = await get_lamp_response()
    lamp_response["state"] = "offline"
    lamp_response["id"] = ITEM_UUID
    resp = MockResponse(lamp_response, 200)
    mocker.patch("aiohttp.ClientSession.request", return_value=resp)

    await ya_client.check_capability(ITEM_UUID, "on_off")

    assert ya_client.quarantine_get(ITEM_UUID).data == {
        "actions": [DeviceCapabilityAction(device_id=ITEM_UUID, capabilities=[("on_off", "on", False)])]
    }


@pytest.mark.asyncio
async def test_check_error(mocker, device):
    ITEM_UUID, DEVICE, ACTIONS_LIST = device
    ya_client = YandexClient()
    lamp_response = await get_lamp_response()
    lamp_response["capabilities"][2]["state"]["value"] = False
    lamp_response["id"] = ITEM_UUID
    resp = MockResponse(lamp_response, 200)
    mocker.patch("aiohttp.ClientSession.request", return_value=resp)

    ya_client.states_set(ITEM_UUID, StateItem(actions_list=ACTIONS_LIST, excl=()))  # action emulate
    with pytest.raises(InfraCheckError) as e_info:
        await ya_client._check_devices_capabilities(ACTIONS_LIST)
        assert e_info.device_ids == [ITEM_UUID]


@pytest.mark.asyncio
async def test_states_dont_check(mocker, device):
    ITEM_UUID, DEVICE, ACTIONS_LIST = device
    ya_client = YandexClient()
    action_response = await get_action_response()
    action_response["devices"][0]["id"] = ITEM_UUID
    resp = MockResponse(action_response, 200)
    mocker.patch("aiohttp.ClientSession.request", return_value=resp)

    await ya_client.change_devices_capabilities(
        [DeviceCapabilityAction(device_id=ITEM_UUID, capabilities=[("on_off", "on", True)])], check=False
    )
    assert not ya_client.states_in(ITEM_UUID)


@pytest.mark.asyncio
async def test_states(mocker, device_f):
    ITEM_UUID, DEVICE, ACTIONS_LIST = device_f
    ya_client = YandexClient()
    action_response = await get_action_response()
    action_response["devices"][0]["id"] = ITEM_UUID
    resp = MockResponse(action_response, 200)
    mocker.patch("aiohttp.ClientSession.request", return_value=resp)

    await ya_client.devices_action(
        ACTIONS_LIST,
        checkable=True,
    )
    assert ya_client.states_get(ITEM_UUID).actions_list == [
        DeviceCapabilityAction(device_id=ITEM_UUID, capabilities=[("on_off", "on", False)])
    ]
    assert ya_client.states_get(ITEM_UUID).checked is False

    lamp_response = await get_lamp_response()
    lamp_response["id"] = ITEM_UUID
    resp = MockResponse(lamp_response, 200)
    mocker.patch("aiohttp.ClientSession.request", return_value=resp)

    await ya_client._check_devices_capabilities(ACTIONS_LIST)
    assert ya_client.states_get(ITEM_UUID).checked is True


@pytest.mark.asyncio
async def test_locks(mocker, device):
    ITEM_UUID, DEVICE, ACTIONS_LIST = device
    ya_client = YandexClient()
    action_response = await get_action_response()
    action_response["devices"][0]["id"] = ITEM_UUID
    resp = MockResponse(action_response, 200)
    mocker.patch("aiohttp.ClientSession.request", return_value=resp)

    assert await ya_client.ask_permissions([(ITEM_UUID, DEVICE)], 0, datetime.timedelta(minutes=15)) == [ITEM_UUID]
    assert await ya_client.ask_permissions([(ITEM_UUID, DEVICE)], 0, datetime.timedelta(minutes=15)) == [ITEM_UUID]
    assert await ya_client.ask_permissions([(ITEM_UUID, DEVICE)], 1, datetime.timedelta(minutes=15)) == [ITEM_UUID]
    await ya_client.devices_action(
        ACTIONS_LIST,
        checkable=True,
        lock_level=2,
        lock=datetime.timedelta(minutes=15),
    )
    assert await ya_client.ask_permissions([(ITEM_UUID, DEVICE)], 1, datetime.timedelta(minutes=15)) == []
    assert await ya_client.ask_permissions([(ITEM_UUID, DEVICE)], 2, datetime.timedelta(minutes=15)) == [ITEM_UUID]
    assert (
        await ya_client.ask_permissions(
            [
                (
                    ITEM_UUID,
                    Device(
                        id=ITEM_UUID,
                        actions=[Action(type="devices.capabilities.on_off", state={"instance": "on", "value": False})],
                    ).dict(),
                )
            ]
        )
        == []
    )
    assert ya_client.states_get(ITEM_UUID).actions_list == ACTIONS_LIST
