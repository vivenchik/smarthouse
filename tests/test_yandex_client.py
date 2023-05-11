import datetime
import json
import os
from unittest import mock

import aiofiles
import aiohttp
import pytest

from src.lib.base_client.exceptions import YandexCheckError
from src.lib.yandex_client.client import YandexClient
from src.lib.yandex_client.models import Action, Device, DeviceCapabilityAction, StateItem


async def get_lamp_response():
    async with aiofiles.open(os.path.join(os.path.dirname(__file__), "mock_data/lamp_response.json"), mode="r") as f:
        return json.loads(await f.read())


async def get_action_response():
    async with aiofiles.open(os.path.join(os.path.dirname(__file__), "mock_data/action_response.json"), mode="r") as f:
        return json.loads(await f.read())


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
    ITEM_UUID, DEVICE, ACTIONS_list = device
    ya_client = YandexClient()
    resp = MockResponse({}, 500)
    mocker.patch("aiohttp.ClientSession.request", return_value=resp)

    await ya_client.check_capability(ITEM_UUID, "on_off")
    assert ya_client.quarantine_in(ITEM_UUID)


@pytest.mark.asyncio
async def test_retry(mocker, device):
    ITEM_UUID, DEVICE, ACTIONS_list = device
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
    ITEM_UUID, DEVICE, ACTIONS_list = device
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
    ITEM_UUID, DEVICE, ACTIONS_list = device
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
    ITEM_UUID, DEVICE, ACTIONS_list = device
    ya_client = YandexClient()
    lamp_response = await get_lamp_response()
    lamp_response["capabilities"][2]["state"]["value"] = False
    lamp_response["id"] = ITEM_UUID
    resp = MockResponse(lamp_response, 200)
    mocker.patch("aiohttp.ClientSession.request", return_value=resp)

    ya_client.states_set(ITEM_UUID, StateItem(actions_list=ACTIONS_list, excl=()))  # action emulate
    with pytest.raises(YandexCheckError) as e_info:
        await ya_client._check_devices_capabilities(ACTIONS_list)
        assert e_info.device_ids == [ITEM_UUID]


@pytest.mark.asyncio
async def test_states_dont_check(mocker, device):
    ITEM_UUID, DEVICE, ACTIONS_list = device
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
    ITEM_UUID, DEVICE, ACTIONS_list = device_f
    ya_client = YandexClient()
    action_response = await get_action_response()
    action_response["devices"][0]["id"] = ITEM_UUID
    resp = MockResponse(action_response, 200)
    mocker.patch("aiohttp.ClientSession.request", return_value=resp)

    await ya_client.devices_action(
        ACTIONS_list,
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

    await ya_client._check_devices_capabilities(ACTIONS_list)
    assert ya_client.states_get(ITEM_UUID).checked is True


@pytest.mark.asyncio
async def test_locks(mocker, device):
    ITEM_UUID, DEVICE, ACTIONS_list = device
    ya_client = YandexClient()
    action_response = await get_action_response()
    action_response["devices"][0]["id"] = ITEM_UUID
    resp = MockResponse(action_response, 200)
    mocker.patch("aiohttp.ClientSession.request", return_value=resp)

    assert await ya_client.ask_permissions([(ITEM_UUID, DEVICE)], 0, datetime.timedelta(minutes=15)) == [ITEM_UUID]
    assert await ya_client.ask_permissions([(ITEM_UUID, DEVICE)], 0, datetime.timedelta(minutes=15)) == [ITEM_UUID]
    assert await ya_client.ask_permissions([(ITEM_UUID, DEVICE)], 1, datetime.timedelta(minutes=15)) == [ITEM_UUID]
    await ya_client.devices_action(
        ACTIONS_list,
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
    assert ya_client.states_get(ITEM_UUID).actions_list == ACTIONS_list
