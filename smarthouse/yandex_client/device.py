import asyncio
import datetime
import functools
import logging
import time
from typing import Any, List, Optional

from pydantic import BaseModel, Field

from smarthouse.base_client.exceptions import InfraCheckError
from smarthouse.storage import Storage
from smarthouse.storage_keys import SysSKeys
from smarthouse.utils import Singleton
from smarthouse.yandex_client.client import YandexClient
from smarthouse.yandex_client.models import DeviceCapabilityAction

logger = logging.getLogger("root")


class Action:
    def __init__(self, device_id, device_name, excl, debug_log: bool = False):
        self.device_id = device_id
        self.device_name = device_name
        self.excl = excl
        self.debug_log = debug_log
        self.capabilities: List = []

    def add_capability(self, capability):
        self.capabilities.append(capability)
        return self

    def add_capabilities(self, capabilities):
        self.capabilities.extend(capabilities)
        return self

    def clear_capabilities(self):
        self.capabilities = []

    def action_dict(self) -> DeviceCapabilityAction:
        return DeviceCapabilityAction(device_id=self.device_id, capabilities=self.capabilities)

    async def run(
        self, check: bool = True, lock_level=0, lock: datetime.timedelta | None = None, feature_checkable=False
    ):
        return await run([self], check=check, lock_level=lock_level, lock=lock, feature_checkable=feature_checkable)

    async def run_async(
        self, check: bool = True, lock_level=0, lock: datetime.timedelta | None = None, feature_checkable=False
    ):
        return await run_async(
            [self], check=check, lock_level=lock_level, lock=lock, feature_checkable=feature_checkable
        )


async def run(
    actions: list[Action],
    check: bool = True,
    lock_level=0,
    lock: datetime.timedelta | None = None,
    feature_checkable=False,
):
    try:
        res = await YandexClient().change_devices_capabilities(
            actions_list=[action.action_dict() for action in actions],
            check=check,
            excl={action.device_id: action.excl for action in actions},
            lock_level=lock_level,
            lock=lock,
            feature_checkable=feature_checkable,  # todo: check feature_checkable after specified timeout
        )
        begin = ""
        if len(actions) > 1 and any(action.debug_log for action in actions):
            logger.debug(f"{len(actions)} actions:")
            begin = "    "
        for action in actions:
            if action.debug_log:
                logger.debug(
                    f"{begin}{action.device_name} :: "
                    + ", ".join(
                        f"{capability_name}.{capability_instance}:{capability_value}"
                        for capability_name, capability_instance, capability_value in action.action_dict().capabilities
                    )
                )
        return res
    except Exception as exc:
        raise exc
    finally:
        pass


class RunQueuesSet(metaclass=Singleton):
    def init(self):
        self.run = asyncio.Queue()
        self.check_and_run = asyncio.Queue()


async def run_async(
    actions: list[Action],
    check: bool = True,
    lock_level=0,
    lock: datetime.timedelta | None = None,
    feature_checkable=False,
):
    if lock is not None:
        for action in actions:
            YandexClient().locks_set(action.device_id, time.time() + lock.total_seconds(), level=lock_level)
    await RunQueuesSet().run.put(
        {
            "actions": actions,
            "check": check,
            "lock_level": lock_level,
            "lock": lock,
            "feature_checkable": feature_checkable,
        }
    )
    storage = Storage()
    storage.put(SysSKeys.max_run_queue_size, max(storage.get(SysSKeys.max_run_queue_size), RunQueuesSet().run.qsize()))


async def check_and_run(
    actions: list[Action],
    lock_level=0,
    lock: datetime.timedelta | None = None,
):
    try:
        await YandexClient()._check_devices_capabilities(
            actions_list=[action.action_dict() for action in actions],
            excl={action.device_id: action.excl for action in actions},
            err_retry=False,
        )
    except InfraCheckError:
        return await run(actions, lock_level=lock_level, lock=lock)


async def check_and_run_async(
    actions: list[Action],
    lock_level=0,
    lock: datetime.timedelta | None = None,
):
    if lock is not None:
        for action in actions:
            YandexClient().locks_set(action.device_id, time.time() + lock.total_seconds(), level=lock_level)
    await RunQueuesSet().check_and_run.put({"actions": actions, "lock_level": lock_level, "lock": lock})
    storage = Storage()
    storage.put(
        SysSKeys.max_check_and_run_queue_size,
        max(storage.get(SysSKeys.max_check_and_run_queue_size), RunQueuesSet().check_and_run.qsize()),
    )


class Response(BaseModel):
    result: Any
    timestamp: float = Field(default_factory=time.time)
    quarantine: bool


class Device:
    def __init__(
        self,
        device_id,
        name: str = "",
        ping=True,
        human_time_func=lambda timestamp=None: (timestamp or time.time()) + 15 * 60,
        use_china_client=False,
        outdated: bool = False,
        debug_log=False,
    ):
        self.device_id = device_id
        self.name = name
        self.ya_client = YandexClient()
        self.excl: tuple[tuple[str, str], ...] = ()
        self.debug_log = debug_log

        self.ya_client.register_device(self.device_id, self.name, ping, human_time_func, outdated, use_china_client)

    async def info(self, hash_seconds: float | None = 1):
        return await self.ya_client.device_info(self.device_id, hash_seconds=hash_seconds)

    async def check_capability(self, capability_name, hash_seconds: float | None = 1):
        return await self.ya_client.check_capability(self.device_id, capability_name, hash_seconds=hash_seconds)

    async def check_capability_instance(self, capability_instance_name, hash_seconds: float | None = 1):
        return await self.ya_client.check_capability_instance(
            self.device_id, capability_instance_name, hash_seconds=hash_seconds
        )

    async def check_property(self, property_name, process_last=False, hash_seconds: float | None = 1):
        # todo: process_last, defaults, quarantine here
        return await self.ya_client.check_property(
            self.device_id, property_name, process_last=process_last, hash_seconds=hash_seconds
        )

    def in_quarantine(self):
        return self.ya_client.quarantine_in(self.device_id)

    def quarantine(self):
        return self.ya_client.quarantine_get(self.device_id)

    def action(self) -> Action:
        return Action(self.device_id, self.name, self.excl, self.debug_log)


def make_response(func):
    @functools.wraps(func)
    async def wrapper(device: Device, *args, **kwargs) -> Response:
        return Response(result=await func(device, *args, **kwargs), quarantine=device.in_quarantine())

    return wrapper


class ControlDevice(Device):
    async def is_on(self, hash_seconds: float | None = 1):
        return await self.check_capability("on_off", hash_seconds=hash_seconds)

    def on(self) -> Action:
        return self.action().add_capability(("on_off", "on", True))

    def off(self) -> Action:
        return self.action().add_capability(("on_off", "on", False))


class Switch(ControlDevice):
    pass


class SwitchLamp(ControlDevice):
    pass


class LuxSensor(Device):
    @make_response
    async def illumination(self, process_last=False, hash_seconds: float | None = 1):
        response = await self.check_property("illumination", process_last=process_last, hash_seconds=hash_seconds)
        return response[0]


class MotionSensor(LuxSensor):
    async def motion_time(self, hash_seconds: float | None = 1):
        response = await self.check_property("motion", hash_seconds=hash_seconds)
        return time.time() - response[1]


class Door(Device):
    async def open_time(self, hash_seconds: float | None = 1):
        response = await self.check_property("open", hash_seconds=hash_seconds)
        return time.time() - response[1]

    async def closed(self, hash_seconds: float | None = 1):
        response = await self.check_property("open", hash_seconds=hash_seconds)
        return response[0] == "closed"


class HumiditySensor(Device):
    @make_response
    async def humidity(self, hash_seconds: float | None = 1):
        response = await self.check_property("humidity", hash_seconds=hash_seconds)
        return response[0]


class AirSensor(HumiditySensor):
    @make_response
    async def temperature(self, hash_seconds: float | None = 1):
        response = await self.check_property("temperature", hash_seconds=hash_seconds)
        return response[0]


class AirCleaner(ControlDevice, AirSensor):
    pass


class TemperatureLamp(ControlDevice):
    async def color_setting(self, hash_seconds: float | None = 1):
        return await self.check_capability_instance("color_setting", hash_seconds=hash_seconds)

    def _fix_temperature_k(self, temperature_k):
        return min(6500, max(1500, int(temperature_k))) if temperature_k is not None else None

    def _fix_brightness(self, brightness):
        return min(100, max(0, int(brightness))) if brightness is not None else None

    def on_brightness(self, brightness: Optional[int] = 100) -> Action:
        if brightness is None:
            return self.on()

        brightness = self._fix_brightness(brightness)

        if brightness == 0:
            return self.off()

        return self.on().add_capability(("range", "brightness", brightness))

    def on_temp(self, temperature_k=4500, brightness=100) -> Action:
        brightness = self._fix_brightness(brightness)

        if temperature_k is None or brightness == 0 or brightness is None:
            return self.on_brightness(brightness)

        temperature_k = self._fix_temperature_k(temperature_k)

        return self.on_brightness(brightness).add_capability(("color_setting", "temperature_k", temperature_k))


class HSVLamp(TemperatureLamp):
    def on_hsv(self, hsv: tuple[int, int, int], brightness=100) -> Action:
        brightness = self._fix_brightness(brightness)

        if hsv is None or brightness == 0 or brightness is None:
            return self.on_brightness(brightness)

        return self.on_brightness(brightness).add_capability(
            ("color_setting", "hsv", {"h": hsv[0], "s": hsv[1], "v": hsv[2]})
        )


def yandex_big_lamp_mutation(action: DeviceCapabilityAction) -> DeviceCapabilityAction:
    patched_capabilities = []
    for needed_capability in action.capabilities:
        if needed_capability[1] == "brightness":
            patched_capabilities.append(
                (
                    needed_capability[0],
                    needed_capability[1],
                    (needed_capability[2], min(needed_capability[2] + 1, 100)),
                )
            )
        else:
            patched_capabilities.append(needed_capability)
    return DeviceCapabilityAction(device_id=action.device_id, capabilities=patched_capabilities)


class YandexBigHSVLamp(HSVLamp):
    def __init__(self, device_id, name: str = ""):
        super().__init__(device_id, name)
        self.ya_client.register_mutation(self.device_id, yandex_big_lamp_mutation)


class RGBLamp(TemperatureLamp):
    def on_rgb(self, rgb: int, brightness=100) -> Action:
        brightness = self._fix_brightness(brightness)

        if rgb is None or brightness == 0 or brightness is None:
            return self.on_brightness(brightness)

        return self.on_brightness(brightness).add_capability(("color_setting", "rgb", rgb))


class Cleaner(ControlDevice):
    def __init__(
        self,
        device_id,
        name: str = "",
        ping=True,
        human_time_func=lambda timestamp=None: (timestamp or time.time()) + 15 * 60,
        use_china_client=False,
        debug_log=False,
    ):
        super().__init__(device_id, name, ping, human_time_func, use_china_client, debug_log)

        self.excl = (("on_off", "on"),)

    async def battery_level(self, hash_seconds: float | None = 1):
        response = await self.check_property("battery_level", hash_seconds=hash_seconds)
        return response[0]

    def on(self, work_speed="fast") -> Action:
        return super().on().add_capability(("mode", "work_speed", work_speed))

    def change_work_speed(self, work_speed="quiet") -> Action:
        return self.action().add_capability(("mode", "work_speed", work_speed))


class Humidifier(ControlDevice, HumiditySensor):
    async def water_level(self, process_last=False, hash_seconds: float | None = 1):
        response = await self.check_property("water_level", process_last=process_last, hash_seconds=hash_seconds)
        return response[0]


class HumidifierOld(Humidifier):
    def on(self, fan_speed="auto") -> Action:
        return super().on().add_capability(("mode", "fan_speed", fan_speed))


class Button(ControlDevice):
    async def button(self, hash_seconds: float | None = 1):
        response = await self.check_property("button", hash_seconds=hash_seconds)
        return response


class Curtain(Device):
    def open(self, open=100) -> Action:
        return self.action().add_capability(("range", "open", open))

    def close(self) -> Action:
        return self.action().add_capability(("range", "open", 0))
