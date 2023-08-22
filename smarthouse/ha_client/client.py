import time
from typing import Any

from homeassistant_api import Client, Domain

from smarthouse.base_client.client import BaseClient
from smarthouse.base_client.exceptions import DeviceOffline, InfraServerError, ProgrammingError
from smarthouse.base_client.utils import retry
from smarthouse.ha_client.models import ActionRequestModel, DeviceInfoResponse

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


class HAClient(BaseClient[DeviceInfoResponse, ActionRequestModel]):
    base_url: str
    prod: bool
    client: Client

    domains: dict[str, Domain]

    async def init(self, base_url: str, ha_token: str, prod: bool = False) -> None:
        self.base_url = base_url
        self.prod = prod
        self.client = Client(f"{base_url}/api/", ha_token, use_async=True)

        self.domains = {
            "light": await self.client.async_get_domain("light"),  # type: ignore[assignment]
        }

    async def get_state(self, entity_id):
        return (await self.client.async_get_entity(entity_id=entity_id)).state.state

    @retry
    async def _device_info(
        self, device_id: str, dont_log: bool = False, err_retry: bool = True, hash_seconds=1
    ) -> DeviceInfoResponse:
        try:
            state = await self.get_state(device_id)
        except Exception as exc:
            raise ProgrammingError(
                f"Device {self.names.get(device_id, device_id)} is unexpected {exc}",
                self.prod,
                device_ids=[device_id],
                debug_str=f"/todo/{self.names.get(device_id, device_id)}",
                dont_log=False,
                err_retry=err_retry,
            ) from exc
        try:
            device = DeviceInfoResponse(state=state)
        except ValueError as exc:
            raise InfraServerError(
                f"Incorrect response format {self.names.get(device_id, device_id)} {exc}",
                self.prod,
                device_ids=[device_id],
                debug_str=f"/devices/{self.names.get(device_id, device_id)}, state: {state}",
                dont_log=dont_log,
                err_retry=err_retry,
            ) from exc
        if device.state == "unavailable":
            raise DeviceOffline(
                f"Device {self.names.get(device_id, device_id)} is offline",
                self.prod,
                device_ids=[device_id],
                debug_str=f"/devices/{self.names.get(device_id, device_id)}",
                dont_log=dont_log,
                err_retry=err_retry,
            )
        return device

    async def check_property(self, device_id: str, property_name: str, proceeded_last=False, hash_seconds=1):
        default = DEFAULTS["property"][property_name]
        device = await self.device_info(device_id, proceeded_last=proceeded_last, hash_seconds=hash_seconds)
        if device is None:
            return default[0], default[1]()
        return device.state, time.time()  # todo
