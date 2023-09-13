import asyncio
import datetime
import functools
import time
from typing import Callable, Union

from smarthouse.logger import logger
from smarthouse.storage import Storage
from smarthouse.utils import HOUR, MIN, get_timedelta_now


def calc_sleep(
    interval: tuple[
        Union[datetime.timedelta, Callable[[], datetime.timedelta]],
        Union[datetime.timedelta, Callable[[], datetime.timedelta]],
    ]
    | None = None
):
    if interval is None:
        return 0

    timedelta_now = get_timedelta_now()
    interval_0: datetime.timedelta = (
        interval[0]()  # type: ignore[operator,assignment]
        if isinstance(interval[0], Callable)  # type: ignore[arg-type]
        else interval[0]
    )
    interval_1: datetime.timedelta = (
        interval[1]()  # type: ignore[operator,assignment]
        if isinstance(interval[1], Callable)  # type: ignore[arg-type]
        else interval[1]
    )

    if interval_0 <= interval_1:
        if not interval_0 <= timedelta_now < interval_1:
            return (
                interval_0 - timedelta_now
                if timedelta_now < interval_0
                else interval_0 + datetime.timedelta(hours=24) - timedelta_now
            ).total_seconds()
    elif interval_1 <= timedelta_now < interval_0:
        return (timedelta_now - interval_0).total_seconds()

    return 0


def looper(
    timeout: int | float,
    interval: tuple[
        Union[datetime.timedelta, Callable[[], datetime.timedelta]],
        Union[datetime.timedelta, Callable[[], datetime.timedelta]],
    ]
    | None = None,
):
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            last_written = time.time()
            calls_time = 0.0
            calls_count = 0
            exceptions_count = 0
            while True:
                try:
                    sleep = calc_sleep(interval)
                    if last_written + 24 * HOUR < time.time() + sleep:
                        last_written = time.time()
                        if calls_time > 10:
                            logger.debug(f"{func.__name__} {calls_count} {int(calls_time)}")
                        calls_time = 0.0
                        calls_count = 0

                    await asyncio.sleep(sleep)

                    start = time.time()
                    sleep = await func(*args, **kwargs)
                    calls_time += time.time() - start
                    calls_count += 1

                    exceptions_count = 0
                except Exception as exc:
                    logger.exception(exc)

                    exceptions_count += 1
                    if exceptions_count > 10:
                        raise exc

                    sleep = 1

                    storage = Storage()
                    await storage.messages_queue.put({"message": f"{func.__name__} {exc}"})

                    await asyncio.sleep(10)

                await asyncio.sleep(sleep or timeout)

        wrapper._original = func
        return wrapper

    return decorator


def scheduler(schedules: tuple[Union[datetime.timedelta, Callable[[], datetime.timedelta]], ...]):
    def decorator(func):
        @looper(MIN)
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            key_name = f"__{func.__name__}"

            timedelta_now = get_timedelta_now()
            for schedule in schedules:
                if isinstance(schedule, Callable):
                    schedule_time = schedule()
                else:
                    schedule_time = schedule

                storage = Storage()
                if (
                    timedelta_now > schedule_time
                    and (timedelta_now - schedule_time).total_seconds() < 2 * MIN
                    and time.time() - storage.get(key_name) > 3 * MIN
                ):
                    result = await func(*args, **kwargs)
                    storage.put(key_name, time.time())
                    return result

        wrapper._original = func
        return wrapper

    return decorator
