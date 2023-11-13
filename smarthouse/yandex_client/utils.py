from typing import Any

from smarthouse.yandex_client.models import DeviceInfoResponse


def get_current_capabilities(device_info: DeviceInfoResponse | None) -> list[tuple[str, str, Any]] | None:
    if device_info is None:
        return []
    capabilities = []
    for capability in device_info.capabilities:
        capabilities.append(
            (
                capability.type[len("devices.capabilities.") :],
                capability.state["instance"],
                capability.state["value"],
            )
        )
    return capabilities
