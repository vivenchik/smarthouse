from unittest.mock import AsyncMock

import pytest

from src.example.scenarios.away_scenarios import away_actions
from tests.test_yandex_client import get_action_response, get_lamp_response


async def ya_client_response(*args, **kwargs):
    if args[1] == "GET":
        return await get_lamp_response()
    if args[1] == "POST":
        return await get_action_response()


@pytest.mark.asyncio
async def test_away_actions_away(mocker, ya_client_mock):
    mocker.patch("asyncio.sleep", new_callable=AsyncMock)
    mocker.patch("src.home.yandex_client.client.YandexClient._request", new=ya_client_response)
    result = await away_actions._original()

    assert result == 1
    # assert ya_client_mock.run_scenario.call_count == 4
    # assert ya_client_mock.change_cleaner_on.call_count == 1
    # assert ya_client_mock.change_humidifier_on.call_count == 1
    # assert ya_client_mock.check_on.call_count == 0
    # assert ya_client_mock.check_battery_level.call_count == 0
    # assert ya_client_mock.change_devices_on.call_count == 1


@pytest.mark.asyncio
async def test_away_actions_return(mocker, ya_client_mock):
    # ya_client_mock.check_door_new.return_value = time.time()
    mocker.patch("src.home.yandex_client.client.YandexClient._request", new=ya_client_response)

    result = await away_actions._original()

    assert result == 1
    # assert ya_client_mock.run_scenario.call_count >= 1
    # assert ya_client_mock.change_cleaner_on.call_count == 1
    # assert ya_client_mock.change_humidifier_on.call_count >= 1
    # assert ya_client_mock.check_on.call_count == 0
    # assert ya_client_mock.check_battery_level.call_count == 0
    # assert ya_client_mock.change_devices_on.call_count == 0


# @pytest.mark.asyncio
# async def test_detect_human_human_detected(mocker, ya_client_mock):
#     device_id = "device_id"
#
#     ya_client_mock.states[device_id] = StateItem(actions_list=[], excl=(), checked=True, timestamp=time.time() - 10)
#     ya_client_mock._check_devices_capabilities = AsyncMock(
#         side_effect=[
#             YandexCheckError("human detected", True, [device_id]),
#             YandexCheckError("human detected", True, [device_id]),
#         ]
#     )
#
#     mocker.patch("asyncio.sleep", new_callable=AsyncMock)
#     await detect_human._original()
#
#     assert device_id not in ya_client_mock.states
#     assert device_id in ya_client_mock._locks
#     assert ya_client_mock._locks[device_id].level == 10
#     messages = []
#     storage = Storage()
#     while not storage.messages_queue.empty():
#         messages.append(storage.messages_queue.get_nowait())
#     assert ["go away", f"detected human: {device_id} human detected"] == messages


# @pytest.mark.asyncio
# async def test_lights_off_actions_turns_lights_off(ya_client_mock):
#     ya_client_mock.check_on.side_effect = [True, False, False]
#     ya_client_mock.check_sensor_motion.return_value = time.time() - 7 * 60
#     await lights_off_actions._original()
#     assert ya_client_mock.change_devices_on.call_count == 1


# @pytest.mark.asyncio
# async def test_lights_off_actions_does_not_turn_lights_off_if_recent_motion(ya_client_mock):
#     ya_client_mock.check_on.side_effect = [True, False, False]
#     ya_client_mock.check_sensor_motion.return_value = time.time() - 2 * 60
#     await lights_off_actions._original()
#     ya_client_mock.change_devices_on.assert_not_called()


# @pytest.mark.asyncio
# async def test_lights_off_actions_does_not_turn_lights_off_if_term_id_quarantined(ya_client_mock):
#     config = get_config()
#     ya_client_mock.check_on.side_effect = [True, False, False]
#     ya_client_mock.check_sensor_motion.return_value = time.time() - 7 * 60
#     ya_client_mock.quarantine_in = lambda x: x == config.term_id
#     await lights_off_actions._original()
#     ya_client_mock.change_devices_on.assert_called_once_with(
#         [config.lamp_e_1_id, config.lamp_e_2_id, config.lamp_e_3_id], False
#     )


# @pytest.mark.asyncio
# async def test_lights_off_actions_does_not_turn_lights_off_if_room_sensor_add_quarantined(ya_client_mock):
#     config = get_config()
#     ya_client_mock.check_on.side_effect = [True, False, False]
#     ya_client_mock.check_sensor_motion.return_value = time.time() - 3 * 60
#     ya_client_mock.quarantine_in = lambda x: x == config.room_sensor_add_id
#     await lights_off_actions._original()
#     ya_client_mock.change_devices_on.assert_called_once_with(
#         [config.lamp_e_1_id, config.lamp_e_2_id, config.lamp_e_3_id], False
#     )
