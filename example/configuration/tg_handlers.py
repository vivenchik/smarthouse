import datetime
import sys
import time

import aiofiles
from telegram import Update

from example.configuration.config import get_config
from example.configuration.device_set import get_device_name
from example.configuration.storage_keys import SKeys
from home.logger import logger
from home.storage import Storage
from home.telegram_client import TGClient
from home.utils import get_time, get_timedelta_now
from home.yandex_client.client import YandexClient


async def restart_handler(tg_client: TGClient, update: Update):
    if update.message is None:
        return
    logger.info("exited by user")
    await tg_client.write_tg("exited by user", replay_message_id=update.message.id)
    await Storage()._write_storage(force=True)
    sys.exit(0)


async def pause_handler(tg_client: TGClient, update: Update):
    if update.message is None:
        return
    config = get_config()
    logger.info("paused")
    config.pause = True
    await tg_client.write_tg("done", replay_message_id=update.message.id)


async def start_handler(tg_client: TGClient, update: Update):
    if update.message is None:
        return
    config = get_config()
    logger.info("started")
    config.pause = False
    await tg_client.write_tg("done", replay_message_id=update.message.id)


async def get_quarantine_handler(tg_client: TGClient, update: Update):
    if update.message is None:
        return
    ya_client = YandexClient()
    await tg_client.write_tg(
        "\n".join(
            [
                f"{await get_device_name(k)}: {round((time.time() - v.timestamp) / 60)} mins"
                for k, v in ya_client._quarantine.items()
            ]
        )
        or "nothing",
        replay_message_id=update.message.id,
        to_delete=True,
        to_delete_timestamp=time.time() + datetime.timedelta(minutes=5).total_seconds(),
    )


async def get_stats_handler(tg_client: TGClient, update: Update):
    if update.message is None:
        return
    ya_client = YandexClient()
    filtered = {}
    for k, v in ya_client._gss.items():
        if (stats := v.stats(ya_client.quarantine_in(k))) > 0:
            filtered[k] = stats

    await tg_client.write_tg(
        "\n".join([f"{await get_device_name(k)}: {round(v * 100, 2)}%" for k, v in filtered.items()]) or "nothing",
        replay_message_id=update.message.id,
        to_delete=True,
        to_delete_timestamp=time.time() + datetime.timedelta(minutes=5).total_seconds(),
    )


async def minimize_lights_handler(tg_client: TGClient, update: Update):
    if update.message is None:
        return
    storage = Storage()
    storage.put(SKeys.max_brightness, 0.4)
    await tg_client.write_tg(
        "done",
        replay_message_id=update.message.id,
        to_delete=True,
        to_delete_timestamp=time.time() + datetime.timedelta(minutes=1).total_seconds(),
    )


async def b1_lights_handler(tg_client: TGClient, update: Update):
    if update.message is None:
        return
    storage = Storage()
    storage.put("__click_click", time.time())
    await tg_client.write_tg(
        "done",
        replay_message_id=update.message.id,
        to_delete=True,
        to_delete_timestamp=time.time() + datetime.timedelta(minutes=1).total_seconds(),
    )


async def b2_lights_handler(tg_client: TGClient, update: Update):
    if update.message is None:
        return
    storage = Storage()
    storage.put("__click_double_click", time.time())
    await tg_client.write_tg(
        "done",
        replay_message_id=update.message.id,
        to_delete=True,
        to_delete_timestamp=time.time() + datetime.timedelta(minutes=1).total_seconds(),
    )


async def b3_lights_handler(tg_client: TGClient, update: Update):
    if update.message is None:
        return
    storage = Storage()
    storage.put("__click_long_press", time.time())
    await tg_client.write_tg(
        "done",
        replay_message_id=update.message.id,
        to_delete=True,
        to_delete_timestamp=time.time() + datetime.timedelta(minutes=1).total_seconds(),
    )


async def remove_alarm_lights_handler(tg_client: TGClient, update: Update):
    if update.message is None:
        return
    storage = Storage()
    storage.delete(SKeys.alarm)
    await tg_client.write_tg(
        "done",
        replay_message_id=update.message.id,
        to_delete=True,
        to_delete_timestamp=time.time() + datetime.timedelta(minutes=60).total_seconds(),
    )


async def water_done_handler(tg_client: TGClient, update: Update):
    if update.message is None:
        return
    storage = Storage()
    storage.put(SKeys.cleanups, 0)
    await tg_client.write_tg(
        "done",
        replay_message_id=update.message.id,
        to_delete=True,
        to_delete_timestamp=time.time() + datetime.timedelta(minutes=1).total_seconds(),
    )


async def log_file_handler(tg_client: TGClient, update: Update):
    await tg_client.write_tg_document("./main.log")


async def storage_file_handler(tg_client: TGClient, update: Update):
    await tg_client.write_tg_document("./storage/storage.yaml")


async def alarm_handler(tg_client: TGClient, update: Update):
    if update.message is None or update.message.text is None:
        return
    storage = Storage()
    needed_alarm = tuple(map(int, update.message.text.lstrip("/").split(":")))
    needed_alarm_datetime = get_time()
    if get_timedelta_now() > datetime.timedelta(hours=needed_alarm[0], minutes=needed_alarm[1]):
        needed_alarm_datetime += datetime.timedelta(days=1)
    needed_alarm_datetime = needed_alarm_datetime.replace(
        hour=needed_alarm[0], minute=needed_alarm[1], second=0, microsecond=0
    )

    storage.put(SKeys.alarm, needed_alarm_datetime.isoformat())
    await tg_client.write_tg(
        "done",
        replay_message_id=update.message.id,
        to_delete=True,
        to_delete_timestamp=time.time() + datetime.timedelta(minutes=10).total_seconds(),
    )


async def log_lines_handler(tg_client: TGClient, update: Update):
    if update.message is None or update.message.text is None:
        return
    message = update.message.text
    debug = message.endswith("d")
    try:
        count = int(message.lstrip("/").rstrip("d"))
    except ValueError:
        return
    async with aiofiles.open("./main.log", mode="r") as f:
        content = await f.readlines()
    lines = [
        line.replace("INFO", "I").replace("ERROR", "E").replace("WARNING", "W").replace("DEBUG", "D")
        for line in content
        if any(level in line for level in ["INFO", "ERROR"] + (["WARNING", "DEBUG"] if debug else []))
    ]
    lines = [line if line.endswith("\n") else line + "\n" for line in lines]
    await tg_client.write_tg(
        "".join(lines[-count:]),
        replay_message_id=update.message.id,
        to_delete=True,
        to_delete_timestamp=time.time() + datetime.timedelta(minutes=15).total_seconds(),
    )


def get_commands():
    return [
        ("b1", "Button one click"),
        ("quarantine", "Get quarantine"),
        ("stats", "Quarantine stats"),
        ("water_done", "Water in cleaner"),
        ("restart", "Restart"),
        ("20", "20 lines of logs"),
        ("b2", "Button double click"),
        ("b3", "Button long press"),
        ("pause", "Pause"),
        ("start", "Start"),
        ("remove_alarm", "Remove alarm"),
        ("minimize_lights", "Set max brightness"),
        ("50d", "50 lines of logs with debug"),
        ("log", "log file"),
        ("storage", "storage file"),
    ]


def get_handlers():
    return [
        (r"/restart", restart_handler),
        (r"/pause", pause_handler),
        (r"/start", start_handler),
        (r"/quarantine", get_quarantine_handler),
        (r"/stats", get_stats_handler),
        (r"/minimize_lights_handler", minimize_lights_handler),
        (r"/b1", b1_lights_handler),
        (r"/b2", b2_lights_handler),
        (r"/b3", b3_lights_handler),
        (r"/remove_alarm", remove_alarm_lights_handler),
        (r"/water_done", water_done_handler),
        (r"/log", log_file_handler),
        (r"/storage", storage_file_handler),
        (r"\d\d:\d\d", alarm_handler),
        (r"\d*d?", log_lines_handler),
    ]
