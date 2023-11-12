import asyncio
import functools

from smarthouse.base_client.exceptions import (
    DeviceOffline,
    InfraCheckError,
    InfraError,
    InfraServerError,
    InfraServerTimeoutError,
    ProgrammingError,
)
from smarthouse.logger import logger


def retry(func):
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        errors = {
            "ise": [0, Exception()],
            "iste": [0, Exception()],
            "pe": [0, Exception()],
            "do": [0, Exception()],
            "ice": [0, Exception()],
            "other": [0, Exception()],
        }
        _exc = Exception()
        while True:
            time_to_sleep = 0
            try:
                return await func(*args, **kwargs)
            except InfraError as exc:
                if isinstance(exc, InfraServerTimeoutError):
                    errors["iste"][0] += 1
                    errors["iste"][1] = exc
                    if errors["iste"][0] >= 3:
                        time_to_sleep = 1 + (errors["iste"][0] - 3) * 0.5
                elif isinstance(exc, InfraServerError):
                    errors["ise"][0] += 1
                    errors["ise"][1] = exc
                    if errors["ise"][0] >= 30:
                        time_to_sleep = 0.1
                elif isinstance(exc, ProgrammingError):
                    errors["pe"][0] += 1
                    errors["pe"][1] = exc
                    if errors["pe"][0] >= 3:
                        time_to_sleep = 0.1
                elif isinstance(exc, DeviceOffline):
                    errors["do"][0] += 1
                    errors["do"][1] = exc
                    time_to_sleep = 0.1
                elif isinstance(exc, InfraCheckError):
                    errors["ice"][0] += 1
                    errors["ice"][1] = exc
                    time_to_sleep = 0.1
                else:
                    errors["other"][0] += 1
                    errors["other"][1] = exc
                    if errors["other"][0] >= 3:
                        time_to_sleep = 0.1

                if not exc.prod or not exc.err_retry:
                    _exc = exc
                    break

            except Exception as exc:
                errors["other"][0] += 1
                errors["other"][1] = exc
                if errors["other"][0] >= 3:
                    time_to_sleep = 0.1

            if errors["iste"][0] >= 10:
                _exc = errors["iste"][1]
                break
            if errors["ise"][0] >= 100:
                _exc = errors["ise"][1]
                break
            if errors["pe"][0] >= 10:
                _exc = errors["pe"][1]
                break
            if errors["do"][0] >= 10:
                _exc = errors["do"][1]
                break
            if errors["ice"][0] >= 10:
                _exc = errors["ice"][1]
                break
            if errors["other"][0] >= 10:
                _exc = errors["other"][1]
                break

            await asyncio.sleep(time_to_sleep)

        if isinstance(_exc, InfraError) and not _exc.dont_log and _exc.debug_str != "":
            logger.debug(_exc.debug_str)
        if not isinstance(_exc, InfraError) or not _exc.dont_log:
            logger.exception(_exc)
        raise _exc

    return wrapper
