import asyncio
import functools

from smarthouse.base_client.exceptions import DeviceOffline, InfraError, InfraServerError, ProgrammingError
from smarthouse.logger import logger


def retry(func):
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        _exc = Exception()
        for i in range(100):
            try:
                if i > 0:
                    await asyncio.sleep(0.1)
                return await func(*args, **kwargs)
            except InfraError as exc:
                _exc = exc
                if not exc.prod or not exc.err_retry:
                    break
                if isinstance(exc, InfraServerError) and i > 100:
                    break
                if isinstance(exc, ProgrammingError) and i > 10:
                    break
                if isinstance(exc, DeviceOffline) and i > 10:
                    break
            except Exception as exc:
                _exc = exc
        if isinstance(_exc, InfraError) and not _exc.dont_log and _exc.debug_str != "":
            logger.debug(_exc.debug_str)
        if not isinstance(_exc, InfraError) or not _exc.dont_log:
            logger.exception(_exc)
        raise _exc

    return wrapper
