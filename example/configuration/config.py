from collections import OrderedDict
from functools import lru_cache

from pydantic import BaseSettings


class Config(BaseSettings):
    prod: bool
    pause: bool = False
    storage_name: str = "storage.yaml"
    s3_mode: bool = False
    iam_mode: bool = False

    yandex_token: str

    telegram_token: str
    telegram_chat_id: str

    auth: str

    ha_url: str = "http://homeassistant:8123"
    ha_token: str

    service_account_id: str
    key_id: str
    private_key: str
    aws_access_key_id: str
    aws_secret_access_key: str

    exit_door_id: str = "cb7f8d6e-fe2f-4f27-956c-6119e95d8922"
    exit_sensor_id: str = "bcf42ffa-bc5a-434d-8952-83b247e20da7"
    room_sensor_id: str = "4bdd2b24-e0a4-425c-8da6-9c0bfea4bafb"
    wc_sensor_id: str = "f8357f4b-5fe0-44dc-a59a-4daf322be44e"
    cleaner_id: str = "d6ceac5b-b79a-4f18-a578-e953dfb26494"
    term_id: str = "369cdfa9-6fab-418f-9090-ccbc3ef0a273"
    lights_wc_1_id: str = "67465ff6-c82c-43a3-bf19-eedc18cad845"
    lights_wc_2_id: str = "96fb0ecb-d28e-4242-9419-6f6aa5b9397e"
    silence_scenario_id: str = "ba73f2d8-dd01-48ab-af1b-acdb9b87f8b5"
    alert_scenario_id: str = "2cdb0dc5-6bc6-49be-b58c-eb33fa666a9e"
    air_id: str = "fbdda7c9-2cae-41cb-aad1-95d418e67593"
    button_id: str = "d433585a-bbbf-4895-8cb5-dbb900da2c71"
    lamp_k_1_id: str = "9b71d877-df5f-4f1f-ab92-a3d17b652c6d"
    lamp_k_2_id: str = "d2758781-cc53-4757-875f-f0d560c655d8"
    lamp_k_3_id: str = "cd6b72c9-e8de-4b9e-b1cf-e641ba3840a0"
    left_lamp_id: str = "e749c17c-c3ec-49f5-8e79-89db06898075"
    right_lamp_id: str = "80164967-b155-48a0-9bbf-077cc13b1280"
    lamp_g_1_id: str = "4b950171-0df0-4b23-aaeb-0f21c7393e73"
    lamp_g_2_id: str = "ed7f9d93-c79e-44b9-985d-0f252a26c894"
    lamp_g_3_id: str = "00d0843e-e6f6-4aa8-9057-28da9dc645c9"
    lamp_g_4_id: str = "f8865444-e149-4a5b-96f8-fc113860c0fa"
    table_lamp_id: str = "d4384c76-3db6-4f16-be39-dfcf04f9744c"
    balcony_lamp_id: str = "5da80b0a-ab93-434d-9a24-065c7cd65b68"
    sofa_lamp_id: str = "3957c326-99ad-4fa7-b098-3484cad82e56"
    humidifier_new_id: str = "7c33b045-930b-4fa9-9994-b956402b3a60"
    air_cleaner_id: str = "b3569bbc-2518-4933-9849-3058bbf9c2fc"
    lamp_e_1_id: str = "2ea89d96-568c-446e-b31d-86d77aa60e98"
    lamp_e_2_id: str = "ca57b793-2617-4712-a002-dde2f82c6b27"
    lamp_e_3_id: str = "1c735a61-d496-4505-8faf-ce7fc6bec180"
    lux_sensor_id: str = "3d580790-00dc-4ce3-9892-a4cdbb346269"
    bed_lamp_id: str = "3114b504-d711-4be5-a119-a09ebddefbe7"
    piano_lamp_id: str = "600e7908-1d8d-4f69-afd4-71ad016ea49e"
    bed_lights_id: str = "177f8cd1-54d4-4eda-a05e-fa99f392cf96"
    main_lamp_id: str = "0cb7362a-f024-4079-a45f-85c4ebf787b2"
    balcony_sensor_id: str = "fc7b8a0c-83f6-4047-a486-309c780f4a29"
    balcony_sensor_2_id: str = "2b5f973c-6243-44d4-bf15-e86378aeaa25"
    balcony_door_id: str = "18461558-ca30-4287-a171-b1f3dda8a4e1"
    clocks_on_scenario_id: str = "18bb2bcd-4e97-4164-a343-5db256549fcc"
    clocks_off_scenario_id: str = "2d4e12e8-e191-4125-a4e3-102c7353e208"
    music_scenario_id: str = "aa198797-c04e-4ea6-a4a5-b829ed7a7ad2"
    ok_scenario_id: str = "57f2de86-d8a9-4ba5-b839-b082658a8e1c"
    curtain_id: str = "de07f975-80ea-445d-b1bf-7d4be0180165"
    hub_power_id: str = "e6a724fb-16a9-444a-85f1-a6b337f3cb56"
    bluetooth_off_scenario_id: str = "c4422669-90ea-4a7c-9755-43a4ac4d71cd"
    button_2_id: str = "289f3efa-4ede-46ac-bdd2-9cd6a7f2d4b7"
    morning_scenario_id: str = "ed351b91-3bfa-44c0-9c09-b5b2d84fdd2f"

    adaptive_interval: tuple[int, int] = (10, 18)
    adaptive_temps: tuple[int, ...] = (6500, 5600, 4500, 3400)

    @property
    def colors(self) -> OrderedDict:
        return OrderedDict(
            red=(0, 96, 100),
            _1=(0, 0, 0),
            kor=(6, 80, 100),
            _2=(0, 0, 0),
            ora=(14, 100, 100),
            _3=(0, 0, 0),
            yel=(25, 96, 100),
            _4=(0, 0, 0),
            sal=(73, 96, 100),
            gre=(135, 96, 100),
            izu=(160, 96, 100),
            bir=(177, 96, 100),
            gol=(190, 96, 100),
            blu=(225, 96, 100),
            # lun=(231, 10, 100),
            sir=(270, 96, 100),
            pur=(280, 96, 100),
            prp=(306, 96, 100),
            pin=(325, 96, 100),
            mal=(340, 100, 100),
            lil=(357, 83, 100),
        )

    class Config:
        env_file = ".env"


@lru_cache()
def get_config() -> Config:
    return Config()  # type: ignore[call-arg]
