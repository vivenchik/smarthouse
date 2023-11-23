import asyncio
import copy
import json
import logging
import time
from typing import Any, Optional

import aiohttp
from async_lru import alru_cache

from smarthouse.base_client.client import BaseClient
from smarthouse.base_client.exceptions import (
    DeviceOffline,
    InfraCheckError,
    InfraServerError,
    InfraServerTimeoutError,
    ProgrammingError,
)
from smarthouse.base_client.utils import retry
from smarthouse.yandex_client.models import (
    Action,
    ActionRequestModel,
    Device,
    DeviceActionResponse,
    DeviceCapabilityAction,
    DeviceInfoResponse,
    StateItem,
)
from smarthouse.yandex_client.utils import get_current_capabilities

logger = logging.getLogger("root")

DEFAULTS: dict[str, dict[str, Any]] = {  # todo: move to devices
    "capability": {"on_off": False},
    "capability_instance": {"color_setting": "hsv"},
    "property": {
        "temperature": (20, time.time),
        "battery_level": (20, time.time),
        "humidity": (35, time.time),
        "illumination": (0, time.time),
        "motion": (0, lambda: time.time() - 100000),
        "open": ("closed", lambda: time.time() - 500000),
        "button": ("click", lambda: time.time() - 1000000000),
        "water_level": (70, time.time),
    },
}


class YandexClient(BaseClient[DeviceInfoResponse, ActionRequestModel]):
    _states: dict[str, StateItem]
    _last: dict[str, tuple[DeviceInfoResponse, float]]
    base_url: str
    client: aiohttp.ClientSession
    prod: bool

    def init(self, yandex_token: str = "", prod: bool = False) -> None:
        super().base_init()

        self.base_url = "https://api.iot.yandex.net"
        self.client = aiohttp.ClientSession(
            base_url=self.base_url,
            headers={"Authorization": f"Bearer {yandex_token}"},
            connector=aiohttp.TCPConnector(
                ssl=False,
                limit=None,  # type: ignore[arg-type]
                force_close=True,
                enable_cleanup_closed=True,
            ),
            timeout=aiohttp.ClientTimeout(total=3),
        )
        self.china_client = aiohttp.ClientSession(
            base_url=self.base_url,
            headers={"Authorization": f"Bearer {yandex_token}"},
            connector=aiohttp.TCPConnector(
                ssl=False,
                limit=None,  # type: ignore[arg-type]
                force_close=True,
                enable_cleanup_closed=True,
            ),
            timeout=aiohttp.ClientTimeout(total=60),
        )
        self.prod = prod

        self._states: dict[str, StateItem] = {}
        self._last: dict[str, DeviceInfoResponse] = {}

    @alru_cache(maxsize=1024, ttl=600)  # todo: remove lru
    async def _request(
        self,
        method: str,
        path: str,
        data: Optional[str] = None,
        use_china_client=False,
        ttl_hash: float | None = None,
    ) -> dict:
        if not self.prod and method == "POST":
            logger.debug(path)

        start = time.time()
        response_data_text = None
        response_data_json = None

        if not use_china_client:
            client_for_request = self.client
        else:
            client_for_request = self.china_client
        try:
            async with client_for_request.request(method, f"/v1.0{path}", data=data) as response:
                if response.content_type == "application/json":
                    response_data_text = await response.text()
                    response_data_json = await response.json()
                else:
                    response_data_text = await response.text()
                    response.raise_for_status()
                    raise InfraServerError(
                        f"Response content type: "
                        f"content_type: '{response.content_type}' is not 'application/json'\n"
                        f" response: {response_data_text}",
                        self.prod,
                        debug_str=f"{method} {path} {data}",
                    )
                response.raise_for_status()

        except json.JSONDecodeError as exc:
            raise InfraServerError(
                f"Response decode error: response: {response_data_text}, exception: {exc}",
                self.prod,
                debug_str=f"{method} {path} {data}",
            ) from exc
        except aiohttp.ClientResponseError as exc:
            if exc.status == 404:
                raise DeviceOffline(
                    f"404 error: response: {response_data_json}, exception: {exc}",
                    self.prod,
                    device_ids=[],
                    debug_str=f"{method} {path} {data}",
                ) from exc
            if exc.status // 100 == 4:
                raise ProgrammingError(
                    f"Client response error: response: {response_data_json}, exception: {exc}",
                    self.prod,
                    debug_str=f"{method} {path} {data}",
                ) from exc
            raise InfraServerError(
                f"Client response error: response: {response_data_json}, exception: {exc}",
                self.prod,
                debug_str=f"{method} {path} {data}",
            ) from exc
        except aiohttp.ClientError as exc:
            raise InfraServerError(
                f"Client error: response: {response_data_json}, exception: {exc}",
                self.prod,
                debug_str=f"{method} {path} {data}",
            ) from exc
        except asyncio.TimeoutError as exc:
            raise InfraServerTimeoutError(
                "Yandex server timeout",
                self.prod,
                debug_str=f"{method} {path} {data}",
            ) from exc

        if path not in self._stats:
            self._stats[path] = 0
        self._stats[path] += time.time() - start

        if response_data_json.get("status") != "ok":
            raise ProgrammingError(
                f"Yandex error: {response_data_json}",
                self.prod,
                debug_str=f"{method} {path} {data}",
            )
        return response_data_json

    @staticmethod
    def get_ttl_hash(seconds: float | None):
        return int(time.time() / seconds) if seconds is not None else time.time()

    async def request(
        self,
        method: str,
        path: str,
        data: Optional[dict] = None,
        use_china_client: bool = False,
        hash_seconds: float | None = 1,
    ) -> dict:
        ttl_hash = self.get_ttl_hash(hash_seconds)
        res = await self._request(method, path, json.dumps(data), use_china_client, ttl_hash)
        if hash_seconds is None:
            self._request.cache_invalidate(method, path, json.dumps(data), use_china_client, ttl_hash)
        return res

    @retry
    async def info(self, hash_seconds: float | None = 1) -> dict:
        return await self.request("GET", "/user/info", hash_seconds=hash_seconds)

    @retry
    async def _device_info(
        self, device_id: str, dont_log: bool = False, err_retry: bool = True, hash_seconds: float | None = 1
    ) -> DeviceInfoResponse:
        use_china_client = self._use_china_client.get(device_id, False)
        if device_id not in self._calls_get:
            self._calls_get[device_id] = 0
        self._calls_get[device_id] += 1
        try:
            response = await self.request(
                "GET", f"/devices/{device_id}", use_china_client=use_china_client, hash_seconds=hash_seconds
            )
        except ProgrammingError as exc:
            exc.dont_log = False
            exc.err_retry = err_retry
            exc.device_ids = [device_id]
            raise exc
        except InfraServerError as exc:
            exc.dont_log = dont_log
            exc.err_retry = err_retry
            exc.device_ids = [device_id]
            raise exc
        except DeviceOffline as exc:
            exc.dont_log = dont_log
            exc.err_retry = err_retry
            exc.device_ids = [device_id]
            raise exc
        except Exception as exc:
            raise ProgrammingError(
                f"Device {self.names.get(device_id, device_id)} is unexpected {exc}",
                self.prod,
                device_ids=[device_id],
                debug_str=f"/devices/{self.names.get(device_id, device_id)}",
                dont_log=False,
                err_retry=err_retry,
            ) from exc
        try:
            device = DeviceInfoResponse(**response)
        except ValueError as exc:
            raise InfraServerError(
                f"Incorrect response format {self.names.get(device_id, device_id)} {exc}",
                self.prod,
                device_ids=[device_id],
                debug_str=f"/devices/{self.names.get(device_id, device_id)}, response: {response}",
                dont_log=dont_log,
                err_retry=err_retry,
            ) from exc
        if device.state != "online":
            raise DeviceOffline(
                f"Device {self.names.get(device_id, device_id)} is offline",
                self.prod,
                device_ids=[device_id],
                debug_str=f"/devices/{self.names.get(device_id, device_id)}",
                dont_log=dont_log,
                err_retry=err_retry,
            )
        for response_property in device.properties:
            if response_property.last_updated == 0.0:
                raise DeviceOffline(
                    f"Device {self.names.get(device_id, device_id)} is may be offline",
                    self.prod,
                    device_ids=[device_id],
                    debug_str=f"/devices/{self.names.get(device_id, device_id)}",
                    dont_log=dont_log,
                    err_retry=err_retry,
                )
        return device

    async def device_info(
        self, device_id: str, ignore_quarantine=False, proceeded_last=False, hash_seconds: float | None = 1
    ) -> DeviceInfoResponse | None:
        result = await super().device_info(
            device_id=device_id,
            ignore_quarantine=ignore_quarantine,
            proceeded_last=proceeded_last,
            hash_seconds=hash_seconds,
        )
        if (device_id not in self.names or self.names[device_id] == "") and result is not None:
            self.register_device(device_id, result.name)
        return result

    async def get_current_capabilities(
        self, device_id: str, hash_seconds: float | None = 1
    ) -> list[tuple[str, str, Any]] | None:
        device_info = await self.device_info(device_id, hash_seconds=hash_seconds)
        return get_current_capabilities(device_info)

    @retry
    async def _devices_action(self, actions_list: list[DeviceCapabilityAction]) -> DeviceActionResponse | None:
        data = ActionRequestModel(
            devices=[
                Device(id=action.device_id, actions=self.get_actions(action.capabilities)) for action in actions_list
            ]
        )
        use_china_client = False
        for _device in data.devices:
            use_china_client |= self._use_china_client.get(_device.id, False)
            if _device.id not in self._calls_post:
                self._calls_post[_device.id] = 0
            self._calls_post[_device.id] += 1
        try:
            response = await self.request(
                "POST", "/devices/actions", data=data.model_dump(), use_china_client=use_china_client, hash_seconds=None
            )
        except ProgrammingError as exc:
            exc.device_ids = [device.id for device in data.devices]
            raise exc
        except InfraServerError as exc:
            exc.device_ids = [device.id for device in data.devices]
            raise exc
        except DeviceOffline as exc:
            exc.device_ids = [device.id for device in data.devices]
            raise exc
        except Exception as exc:
            cleaned_devices = [self.names.get(device.id, device.id) for device in data.devices]
            raise ProgrammingError(
                f"Something is unexpected with devices ({cleaned_devices}) {exc}",
                self.prod,
                device_ids=[device.id for device in data.devices],
                debug_str=f"/devices/actions {cleaned_devices}, request: {data.model_dump()}",
                dont_log=False,
            ) from exc
        try:
            response_struct = DeviceActionResponse(**response)
        except ValueError as exc:
            cleaned_devices = [self.names.get(device.id, device.id) for device in data.devices]
            raise InfraServerError(
                f"Incorrect response ({cleaned_devices}) {exc}",
                self.prod,
                device_ids=[device.id for device in data.devices],
                debug_str=f"/devices/actions {cleaned_devices}, response: {response}",
            ) from exc
        broken_devices = {}
        for device in response_struct.devices:
            for capability in device.capabilities:
                if capability.state.action_result.status != "DONE":
                    broken_devices[device.id] = capability.state.action_result.error_message
        if broken_devices:
            cleaned_broken_devices = {self.names.get(k, k): v for k, v in broken_devices.items()}
            raise DeviceOffline(
                f"Something is going wrong with devices ({cleaned_broken_devices}): {data.model_dump()}",
                self.prod,
                device_ids=list(broken_devices.keys()),
            )
        return response_struct

    @staticmethod
    def get_actions(capabilities: list[tuple[str, str, Any]]) -> list[Action]:
        return [
            Action(
                type=f"devices.capabilities.{capability[0]}", state={"instance": capability[1], "value": capability[2]}
            )
            for capability in capabilities
        ]

    def device_from_action(self, action: DeviceCapabilityAction):
        return Device(id=action.device_id, actions=self.get_actions(action.capabilities))

    async def _check_devices_capabilities(
        self,
        actions_list: list[DeviceCapabilityAction],
        excl: dict[str, tuple[tuple[str, str], ...]] | None = None,
        err_retry: bool = True,
        real_action=True,
        mutated=False,
    ):
        if excl is None:
            excl = {}

        if real_action:
            filtered_ids = await self.ask_permissions([(action.device_id, None) for action in actions_list])
        else:
            filtered_ids = [action.device_id for action in actions_list]
        patched_actions_list: list = []
        wished_actions_list: list = []
        for action in actions_list:
            wished_actions_list.append(copy.deepcopy(action))
            if action.device_id not in filtered_ids:
                patched_actions_list.append(None)
                continue

            if self._mutations.get(action.device_id) is not None and not mutated:
                patched_action = self._mutations[action.device_id](action)
                patched_actions_list.append(patched_action)
            else:
                patched_actions_list.append(action)

        device_ids = [action.device_id for action in patched_actions_list if action is not None]
        tasks = [self.device_info(device_id) for device_id in device_ids]
        devices_info = await asyncio.gather(*tasks)
        devices = {device_ids[i]: device_info for i, device_info in enumerate(devices_info)}

        errors = []
        for i, _ in enumerate(patched_actions_list):
            if (action := patched_actions_list[i]) is None:
                continue
            device_id = action.device_id
            if (device := devices[device_id]) is None:
                continue
            if not self.states_in(device_id):
                continue
            state = self.states_get(device_id)
            if state.actions_list != [actions_list[i]] or state.excl != excl.get(device_id, ()):
                if real_action:
                    logger.debug(
                        f"check aborted. detected conflict: {self.names.get(device_id, device_id)}, "
                        f"{[actions_list[i]]} != {state.actions_list} or {excl.get(device_id, ())} != {state.excl}"
                    )
                continue

            for j, needed_capability in enumerate(action.capabilities):
                for capability in device.capabilities:
                    if capability.type == f"devices.capabilities.{needed_capability[0]}":
                        wished_actions_list[i].capabilities[j] = (
                            needed_capability[0],
                            capability.state["instance"],
                            capability.state["value"],
                        )
                        if capability.state["instance"] != needed_capability[1]:
                            errors.append(
                                (
                                    f'{needed_capability[0]} {needed_capability[1]} -> {capability.state["instance"]}',
                                    device_id,
                                )
                            )
                            continue
                        current_capability_value = capability.state["value"]
                        if (needed_capability[0], needed_capability[1]) not in excl.get(device_id, ()) and not (
                            isinstance(needed_capability[2], tuple)
                            and current_capability_value in needed_capability[2]
                            or current_capability_value == needed_capability[2]
                        ):
                            errors.append(
                                (
                                    f"{needed_capability[0]} {needed_capability[1]} {needed_capability[2]} "
                                    f'-> {capability.state["value"]}',
                                    device_id,
                                )
                            )
                            continue

            if (
                real_action
                and self.states_in(device_id)
                and self.states_get(device_id).actions_list == [actions_list[i]]
                and self.states_get(device_id).excl == excl.get(device_id, ())
            ):
                state = self.states_get(device_id)
                state.checked = True
                self.states_set(device_id, state)

        if len(errors) > 0:
            raise InfraCheckError(
                "\n".join([f"{self.names.get(error[1], error[1])}: {error[0]}" for error in errors]),
                self.prod,
                [error[1] for error in errors],
                wished_actions_list=wished_actions_list,
                err_retry=err_retry,
            )

    @retry
    async def run_scenario(self, scenario_id: str) -> dict:
        return await self.request("POST", f"/scenarios/{scenario_id}/actions", hash_seconds=None)

    @retry
    async def group_info(self, group_id: str, hash_seconds: float | None = 1) -> dict:
        return await self.request("GET", f"/groups/{group_id}", hash_seconds=hash_seconds)

    @retry
    async def group_actions(self, group_id, actions) -> dict:
        data = {"actions": actions}
        return await self.request("POST", f"/groups/{group_id}/actions", data=data, hash_seconds=None)

    async def check_property(
        self, device_id: str, property_name: str, proceeded_last=False, hash_seconds: float | None = 1
    ):
        default = DEFAULTS["property"][property_name]
        device = await self.device_info(device_id, proceeded_last=proceeded_last, hash_seconds=hash_seconds)
        if device is None:
            return default[0], default[1]()
        for response_property in device.properties:
            if response_property.parameters["instance"] == property_name:
                return response_property.state["value"], response_property.last_updated

    async def check_capability(self, device_id: str, capability_name: str, hash_seconds: float | None = 1):
        default = DEFAULTS["capability"][capability_name]

        if (device := await self.device_info(device_id, hash_seconds=hash_seconds)) is None:
            return default
        for capability in device.capabilities:
            if capability.type == f"devices.capabilities.{capability_name}":
                return capability.state["value"]

    async def check_capability_instance(self, device_id: str, capability_name: str, hash_seconds: float | None = 1):
        default = DEFAULTS["capability_instance"][capability_name]

        if (device := await self.device_info(device_id, hash_seconds=hash_seconds)) is None:
            return default
        for capability in device.capabilities:
            if capability.type == f"devices.capabilities.{capability_name}":
                return capability.state["instance"]
