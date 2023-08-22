from pydantic import BaseModel


class DeviceInfoResponse(BaseModel):
    state: str


class ActionRequestModel(BaseModel):
    ...
