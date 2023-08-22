import asyncio
import copy
import datetime
import time
from collections.abc import Callable
from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel

from smarthouse.base_client.exceptions import DeviceOffline, InfraCheckError, InfraServerError
from smarthouse.base_client.gap_stat import GapStat
from smarthouse.base_client.models import LockItem, QuarantineItem
from smarthouse.base_client.utils import retry
from smarthouse.logger import logger
from smarthouse.utils import Singleton
from smarthouse.yandex_client.models import DeviceCapabilityAction, StateItem

DeviceInfoResponseType = TypeVar("DeviceInfoResponseType", bound=BaseModel)
ActionRequestModelType = TypeVar("ActionRequestModelType", bound=BaseModel)


class BaseClient(Generic[DeviceInfoResponseType, ActionRequestModelType], metaclass=Singleton):
    _states: dict[str, StateItem]
    _last: dict[str, DeviceInfoResponseType]
    _quarantine: dict[str, QuarantineItem]
    _locks: dict[str, LockItem]
    _mutations: dict[str, Callable]
    _gss: dict[str, GapStat]
    _stats: dict[str, float]

    messages_queue: asyncio.Queue
    names: dict[str, str]
    _ping: set
    _human_time_funcs: dict

    def base_init(self) -> None:
        self._quarantine: dict[str, QuarantineItem] = {}
        self._locks: dict[str, LockItem] = {}
        self._mutations: dict[str, Callable] = {}
        self._gss: dict[str, GapStat] = {}
        self._stats: dict[str, float] = {}
        self._states: dict[str, StateItem] = {}
        self._last: dict[str, DeviceInfoResponseType] = {}

        self.messages_queue: asyncio.Queue = asyncio.Queue()
        self.names: dict[str, str] = {}
        self._ping: set = set()
        self._human_time_funcs: dict = {}

    def register_device(self, device_id, name, ping=True, human_time_func=lambda: time.time() + 15 * 60):
        self.names[device_id] = name
        if ping:
            self._ping.add(device_id)
        self._human_time_funcs[device_id] = self._human_time_funcs.get(device_id) or human_time_func

    def register_mutation(self, device_id, mutation):
        self._mutations[device_id] = mutation

    def _quarantine_set(self, device_id: str, data: Optional[dict] = None) -> None:
        if data is not None or device_id not in self._quarantine:
            self._quarantine[device_id] = QuarantineItem(data=data)
        if device_id not in self._gss:
            self._gss[device_id] = GapStat()
        self._gss[device_id].add(True)

    def _quarantine_remove(self, device_id: str) -> None:
        self._quarantine.pop(device_id)
        if device_id not in self._gss:
            self._gss[device_id] = GapStat()
        self._gss[device_id].add(False)

    def quarantine_in(self, device_id: str) -> bool:
        return device_id in self._quarantine

    def quarantine_get(self, device_id: str) -> QuarantineItem | None:
        return self._quarantine.get(device_id)

    def quarantine_ids(self) -> set[str]:
        return copy.deepcopy(set(self._quarantine.keys()))

    def locks_set(self, device_id: str, timestamp: float, level: int = 0) -> None:
        self._locks[device_id] = LockItem(level=level, timestamp=timestamp)

    def locks_in(self, device_id: str) -> bool:
        return device_id in self._locks

    def locks_get(self, device_id: str) -> LockItem:
        return self._locks[device_id]

    def locks_remove(self, device_id: str) -> None:
        if device_id in self._locks:
            self._locks.pop(device_id)

    def locks_reset(self) -> None:
        self._locks = {}

    def states_remove(self, device_id: str) -> None:
        if device_id in self._states:
            self._states.pop(device_id)

    def states_set(self, device_id: str, state: StateItem) -> None:
        self._states[device_id] = state

    def states_get(self, device_id: str) -> StateItem:
        return self._states[device_id]

    def states_keys(self):
        return self._states.keys()

    def states_in(self, device_id: str) -> bool:
        return device_id in self._states

    def last_get(self, device_id: str) -> DeviceInfoResponseType:
        return self._last[device_id]

    def last_in(self, device_id: str) -> bool:
        return device_id in self._last

    def last_set(self, device_id: str, response: DeviceInfoResponseType) -> None:
        self._last[device_id] = response

    async def ask_permissions(
        self,
        devices_items: list[tuple[str, Optional[dict]]],
        lock_level=0,
        lock: datetime.timedelta | None = None,
        actions_list: list[DeviceCapabilityAction] | None = None,
    ) -> list[str]:
        filtered_ids = []
        actions_list_dict = {action.device_id: action for action in actions_list} if actions_list else {}
        for device_id, device in devices_items:
            if self.quarantine_in(device_id) and device is not None:
                self._quarantine_set(device_id, {"actions": [actions_list_dict[device_id]]})
                continue
            locked_level = self.locks_get(device_id).level if self.locks_in(device_id) else 0
            locked_time = self.locks_get(device_id).timestamp if self.locks_in(device_id) else None
            if (
                locked_level == 0
                or lock_level >= locked_level
                or not locked_time
                or locked_time
                and time.time() > locked_time
            ):
                filtered_ids.append(device_id)
                if lock is not None and device is not None:
                    self.locks_set(device_id, time.time() + lock.total_seconds(), level=lock_level)

        return filtered_ids

    async def _device_info(
        self, device_id: str, dont_log: bool = False, err_retry: bool = True, hash_seconds=1
    ) -> DeviceInfoResponseType:
        raise Exception()

    async def device_info(
        self, device_id: str, ignore_quarantine=False, proceeded_last=False, hash_seconds=1
    ) -> DeviceInfoResponseType | None:
        if proceeded_last:
            return self.last_get(device_id) if self.last_in(device_id) else None
        try:
            if not ignore_quarantine and self.quarantine_in(device_id):
                return None
            result = await self._device_info(device_id, ignore_quarantine, not ignore_quarantine, hash_seconds)
            self.last_set(device_id, result)
            return result
        except (DeviceOffline, InfraServerError) as exc:
            self.states_remove(device_id)
            self._quarantine_set(device_id)
            if not ignore_quarantine and exc.send:
                await self.messages_queue.put(str(exc))
            return None

    async def _devices_action(self, actions_list: list[DeviceCapabilityAction]) -> Any:
        raise Exception()

    def device_from_action(self, action: DeviceCapabilityAction) -> BaseModel:
        raise Exception()

    async def devices_action(
        self,
        actions_list: list[DeviceCapabilityAction],
        lock_level=0,
        lock: datetime.timedelta | None = None,
        checkable=False,
        excl: dict[str, tuple[tuple[str, str], ...]] | None = None,
    ) -> Any:
        if excl is None:
            excl = {}

        filtered_ids = await self.ask_permissions(
            [(action.device_id, self.device_from_action(action).dict()) for action in actions_list],
            lock_level,
            lock,
            actions_list,
        )
        filtered_actions = [action for action in actions_list if action.device_id in filtered_ids]

        actions_list_dict = {action.device_id: action for action in actions_list} if actions_list else {}
        if checkable and actions_list:
            for action in filtered_actions:
                self.states_set(
                    action.device_id,
                    StateItem(actions_list=[actions_list_dict[action.device_id]], excl=excl.get(action.device_id, ())),
                )

        try:
            return await self._devices_action(filtered_actions)
        except (DeviceOffline, InfraServerError) as exc:
            logger.exception(exc)
            actions_dict = {action.device_id: action for action in actions_list}
            for device_id in exc.device_ids:
                self.states_remove(device_id)
                self._quarantine_set(device_id, {"actions": [actions_dict[device_id]]})

            if exc.send:
                await self.messages_queue.put(str(exc))
            return None

    async def _check_devices_capabilities(
        self,
        actions_list: list[DeviceCapabilityAction],
        excl: dict[str, tuple[tuple[str, str], ...]] | None = None,
        err_retry: bool = True,
        real_action=True,
    ):
        raise Exception()

    @retry
    async def _change_devices_capabilities(
        self,
        actions_list: list[DeviceCapabilityAction],
        check: bool = True,
        excl: dict[str, tuple[tuple[str, str], ...]] | None = None,
        lock_level=0,
        lock: datetime.timedelta | None = None,
        feature_checkable=False,
    ):
        await self.devices_action(actions_list, lock_level, lock, check or feature_checkable, excl)

        if check:
            await self._check_devices_capabilities(actions_list, excl, err_retry=True)

    async def change_devices_capabilities(
        self,
        actions_list: list[DeviceCapabilityAction],
        check: bool = True,
        excl: dict[str, tuple[tuple[str, str], ...]] | None = None,
        lock_level=0,
        lock: datetime.timedelta | None = None,
        feature_checkable=False,
    ):
        try:
            return await self._change_devices_capabilities(
                actions_list, check, excl, lock_level, lock, feature_checkable
            )
        except InfraCheckError as exc:
            for device_id in exc.device_ids:
                self.states_remove(device_id)
            await self.messages_queue.put(str(exc))
