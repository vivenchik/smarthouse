import datetime
import functools
import time

from src.example.configuration.config import get_config
from src.example.scenarios.light_utils import calc_sunset, calc_sunset_datetime
from src.lib.device import (
    AirCleaner,
    AirSensor,
    Button,
    Cleaner,
    Curtain,
    Door,
    HSVLamp,
    Humidifier,
    LuxSensor,
    MotionSensor,
    RGBLamp,
    Switch,
    SwitchLamp,
    YandexBigHSVLamp,
)
from src.lib.utils import Singleton, get_timedelta_now, hsv_to_rgb


def adaptive_human_time_func():
    if datetime.timedelta(hours=10) < get_timedelta_now() < calc_sunset():
        return calc_sunset_datetime().timestamp()
    return time.time() + 15 * 60


class DeviceSet(metaclass=Singleton):
    def init(self):
        config = get_config()
        self.balcony_lamp = SwitchLamp(config.balcony_lamp_id, "Освещение балкон")
        self.wc_1 = SwitchLamp(config.lights_wc_1_id, "Освещение в ванной")
        self.wc_2 = SwitchLamp(config.lights_wc_2_id, "Освещение в ванной у зеркала")
        self.bed_lights = SwitchLamp(config.bed_lights_id, "Освещение спальня")
        self.sofa_lamp = SwitchLamp(config.sofa_lamp_id, "Освещение у дивана")
        self.main_lamp = SwitchLamp(config.main_lamp_id, "Люстра")

        self.exit_sensor = MotionSensor(config.exit_sensor_id, "Датчик движения коридор")
        self.room_sensor = MotionSensor(config.room_sensor_id, "Датчик движения комната")
        self.wc_sensor = MotionSensor(config.wc_sensor_id, "Датчик движения туалет")
        self.balcony_sensor = MotionSensor(config.balcony_sensor_id, "Датчик движения балкон")
        self.balcony_sensor_2 = MotionSensor(config.balcony_sensor_2_id, "Датчик движения балкон 2")

        self.lux_sensor = LuxSensor(config.lux_sensor_id, "Датчик освещенности")

        self.exit_door = Door(config.exit_door_id, "Выходная дверь")
        self.balcony_door = Door(config.balcony_door_id, "Балконная дверь")

        self.air = Switch(config.air_id, "Вытяжка ванная")
        self.hub_power = Switch(config.hub_power_id, "Хаб", ping=False)

        self.wc_term = AirSensor(config.term_id, "Датчик воздуха туалет")
        self.air_cleaner = AirCleaner(config.air_cleaner_id, "Очиститель воздуха")

        self.lamp_e_1 = HSVLamp(config.lamp_e_1_id, "Лампа выход 1")
        self.lamp_e_2 = HSVLamp(config.lamp_e_2_id, "Лампа выход 2")
        self.lamp_e_3 = HSVLamp(config.lamp_e_3_id, "Лампа выход 3")
        self.lamp_k_1 = HSVLamp(config.lamp_k_1_id, "Лампа кухня 1", human_time_func=adaptive_human_time_func)
        self.lamp_k_2 = HSVLamp(config.lamp_k_2_id, "Лампа кухня 2", human_time_func=adaptive_human_time_func)
        self.lamp_k_3 = HSVLamp(config.lamp_k_3_id, "Лампа кухня 3", human_time_func=adaptive_human_time_func)
        self.lamp_g_1 = HSVLamp(config.lamp_g_1_id, "Лампа кухня 4", human_time_func=adaptive_human_time_func)
        self.lamp_g_2 = HSVLamp(config.lamp_g_2_id, "Лампа гостиная 1", human_time_func=adaptive_human_time_func)
        self.lamp_g_3 = HSVLamp(config.lamp_g_3_id, "Лампа гостиная 2", human_time_func=adaptive_human_time_func)
        self.lamp_g_4 = HSVLamp(config.lamp_g_4_id, "Лампа гостиная 3", human_time_func=adaptive_human_time_func)

        self.left_lamp = YandexBigHSVLamp(config.left_lamp_id, "Левая лампа")
        self.right_lamp = YandexBigHSVLamp(config.right_lamp_id, "Правая лампа")

        self.table_lamp = RGBLamp(config.table_lamp_id, "Настольная лампа")
        self.piano_lamp = RGBLamp(config.piano_lamp_id, "Лампа у пианино")
        self.bed_lamp = RGBLamp(config.bed_lamp_id, "Прикроватная лампа")

        self.cleaner = Cleaner(config.cleaner_id, "Пылесос")

        self.humidifier = Humidifier(config.humidifier_id, "Увлажнитель", ping=False)

        self.button = Button(config.button_id, "Кнопка")
        self.button_2 = Button(config.button_2_id, "Кнопка спальня")

        self.curtain = Curtain(config.curtain_id, "Шторы")

    @property
    def all_devices(self):
        return (
            self.table_lamp,
            self.lamp_k_1,
            self.lamp_k_2,
            self.lamp_k_3,
            self.lamp_e_1,
            self.lamp_e_2,
            self.lamp_e_3,
            self.lamp_g_1,
            self.lamp_g_2,
            self.lamp_g_3,
            self.lamp_g_4,
            self.left_lamp,
            self.right_lamp,
            self.balcony_lamp,
            self.sofa_lamp,
            self.bed_lamp,
            self.piano_lamp,
            self.lux_sensor,
            self.air_cleaner,
            self.humidifier,
            self.button,
            self.air,
            self.wc_1,
            self.wc_2,
            self.wc_term,
            self.cleaner,
            self.wc_sensor,
            self.room_sensor,
            self.exit_sensor,
            self.exit_door,
            self.bed_lights,
            self.main_lamp,
            self.balcony_sensor,
            self.balcony_sensor_2,
            self.balcony_door,
            self.curtain,
            # self.hub_power,
            self.button_2,
        )

    @functools.lru_cache
    def find_device(self, device_id):
        for device in self.all_devices:
            if device.device_id == device_id:
                return device
        return None

    @property
    def all_lamps(self):
        return (
            self.table_lamp,
            self.lamp_k_1,
            self.lamp_k_2,
            self.lamp_k_3,
            self.lamp_g_1,
            self.lamp_g_2,
            self.lamp_g_3,
            self.lamp_g_4,
            self.left_lamp,
            self.right_lamp,
            self.balcony_lamp,
            self.sofa_lamp,
            self.bed_lamp,
            self.piano_lamp,
            self.bed_lights,
            self.main_lamp,
        )

    @property
    def adaptive_lamps(self):
        return (
            self.lamp_k_1,
            self.lamp_k_2,
            self.lamp_k_3,
            self.lamp_g_1,
            self.lamp_g_2,
            self.lamp_g_3,
            self.lamp_g_4,
        )

    @property
    def modes(self):
        return (
            [
                self.table_lamp.on_temp(3400),
                self.piano_lamp.on_temp(3400),
                self.bed_lamp.on_temp(3400),
            ],
            [
                self.table_lamp.on_rgb(hsv_to_rgb((340, 40, 100))),
                self.piano_lamp.on_rgb(hsv_to_rgb((231, 10, 100))),
                self.left_lamp.on_hsv((160, 20, 50), 50),
                self.right_lamp.on_hsv((6, 50, 50), 50),
                self.bed_lamp.on_temp(3000, 50),
            ],
            [
                self.table_lamp.on_temp(2700),
                self.piano_lamp.on_temp(2700),
                self.sofa_lamp.on(),
            ],
            [
                self.main_lamp.on(),
                self.left_lamp.on_temp(4500),
                self.right_lamp.on_temp(4500),
            ],
            [
                self.bed_lights.on(),
                self.lamp_k_1.on_temp(3400, 50),
                self.lamp_k_2.on_temp(3400, 50),
                self.lamp_k_3.on_temp(3400, 50),
            ],
        )

    @property
    def paint(self):
        return [
            self.table_lamp.on_temp(3400),
            self.piano_lamp.on_temp(3400),
            self.lamp_k_1.on_temp(3400, 50),
            self.lamp_k_2.on_temp(3400, 50),
            self.lamp_k_3.on_temp(3400, 50),
            self.main_lamp.on(),
            self.sofa_lamp.on(),
            self.balcony_lamp.on(),
        ]

    @property
    def lamp_groups(self):
        return (
            (
                self.table_lamp,
                self.lamp_k_1,
                self.lamp_k_2,
                self.lamp_k_3,
            ),
            (
                self.lamp_g_1,
                self.lamp_g_2,
                self.lamp_g_3,
                self.lamp_g_4,
            ),
            (
                self.bed_lamp,
                self.left_lamp,
                self.right_lamp,
            ),
            (self.piano_lamp,),
        )

    @property
    def alarm_lamps(self):
        return (
            self.bed_lamp,
            self.left_lamp,
            self.right_lamp,
        )


async def get_device_name(device_id: str):
    ds = DeviceSet()
    if (ds_result := ds.find_device(device_id)) is not None:
        return ds_result.name.lower()

    config = get_config()
    config_dict = config.dict()
    inverted_config_dict = {v: k for k, v in config_dict.items()}
    result = inverted_config_dict.get(device_id, "")
    if (result := result[: -len("_id")] if result.endswith("_id") else result) is not None:
        return result

    return device_id
