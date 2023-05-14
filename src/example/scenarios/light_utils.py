import datetime

import astral
import astral.sun

from src.home.utils import add_tz, get_time, time_to_timedelta


def calc_sun(additional_time: datetime.timedelta = datetime.timedelta(minutes=0)):
    location = astral.LocationInfo("Moscow", "Moscow", "Europe/Moscow", 55.727932, 37.589716)
    sun = astral.sun.sun(location.observer, date=get_time().date())
    return add_tz(sun["sunrise"] + additional_time), add_tz(sun["sunset"] + additional_time)


def calc_sunrise(additional_time: datetime.timedelta = datetime.timedelta(minutes=-30)):
    return time_to_timedelta(calc_sun(additional_time)[0])


def calc_sunset(additional_time: datetime.timedelta = datetime.timedelta(minutes=30)):
    return time_to_timedelta(calc_sun(additional_time)[1])


def calc_sunset_datetime(additional_time: datetime.timedelta = datetime.timedelta(minutes=30)):
    return calc_sun(additional_time)[1]
