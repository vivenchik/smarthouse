from typing import Any, Optional

from pydantic import BaseModel


class DeviceCapabilityAction(BaseModel):
    device_id: str
    capabilities: list[tuple[str, str, Any]]


class Capability(BaseModel):
    retrievable: bool
    type: str
    parameters: dict
    state: dict
    last_updated: float


class Properties(BaseModel):
    retrievable: bool
    type: str
    parameters: dict
    state: dict
    last_updated: float


class DeviceInfoResponse(BaseModel):
    status: str
    request_id: str
    id: str
    name: str
    aliases: list[str]
    type: str
    state: str
    groups: list[str]
    room: str
    external_id: str
    skill_id: str
    capabilities: list[Capability]
    properties: list[Properties]
    message: Optional[str]


class Action(BaseModel):
    type: str
    state: dict


class Device(BaseModel):
    id: str
    actions: list[Action]


class ActionRequestModel(BaseModel):
    devices: list[Device]


class ActionResult(BaseModel):
    status: str
    error_message: Optional[str]


class DeviceResponseState(BaseModel):
    instance: str
    action_result: ActionResult


class CapabilityResponse(BaseModel):
    type: str
    state: DeviceResponseState


class DeviceResponse(BaseModel):
    id: str
    capabilities: list[CapabilityResponse]


class DeviceActionResponse(BaseModel):
    status: str
    request_id: str
    devices: list[DeviceResponse]


class StateItem(BaseModel):
    checked: bool = False
    actions_list: list
    excl: tuple[tuple[str, str], ...] = ()
    mutated: bool = False
