import colorsys
import datetime

MIN = 60
HOUR = 60 * MIN


class Singleton(type):
    _instances: dict = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


def add_tz(d: datetime.datetime) -> datetime.datetime:
    return d.astimezone(datetime.timezone(datetime.timedelta(hours=3)))


def get_time() -> datetime.datetime:
    return add_tz(datetime.datetime.now())


def time_to_timedelta(time: datetime.datetime) -> datetime.timedelta:
    return datetime.timedelta(hours=time.hour, minutes=time.minute, seconds=time.second)


def get_timedelta_now() -> datetime.timedelta:
    return time_to_timedelta(get_time())


def hsv_to_rgb(hsv: tuple[int, int, int]):
    r, g, b = colorsys.hsv_to_rgb(hsv[0] / 360, hsv[1] / 100, hsv[2] / 100)
    return int("%02x%02x%02x" % (int(r * 255), int(g * 255), int(b * 255)), 16)
