import datetime
import logging
import sys
import time

import aiofiles
from telegram import Update

from example.configuration.config import get_config
from example.configuration.device_set import get_device_name
from example.configuration.storage_keys import SKeys
from smarthouse.storage import Storage
from smarthouse.storage_keys import SysSKeys
from smarthouse.telegram_client import TGClient
from smarthouse.utils import get_time, get_timedelta_now
from smarthouse.yandex_client.client import YandexClient

logger = logging.getLogger("root")


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
    await tg_client.write_tg_document("./storage/main.log")


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
        f"{needed_alarm_datetime.isoformat()}"[: -len(":00+03:00")],
        replay_message_id=update.message.id,
        to_delete=True,
        to_delete_timestamp=time.time() + datetime.timedelta(minutes=10).total_seconds(),
    )


async def skip_alarm_handler(tg_client: TGClient, update: Update):
    if update.message is None or update.message.text is None:
        return
    storage = Storage()
    alarm = storage.get(SKeys.alarm, None)
    if alarm is None:
        return
    alarm_datetime = datetime.datetime.fromisoformat(alarm)
    new_alarm_datetime = alarm_datetime + datetime.timedelta(days=1)

    storage.put(SKeys.alarm, new_alarm_datetime.isoformat())
    await tg_client.write_tg(
        f"{new_alarm_datetime.isoformat()}"[: -len(":00+03:00")],
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
    async with aiofiles.open("./storage/main.log", mode="r") as f:
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


async def sleep_handler(tg_client: TGClient, update: Update):
    if update.message is None:
        return
    storage = Storage()
    await storage.tasks.put("sleep")
    await tg_client.write_tg(
        "done",
        replay_message_id=update.message.id,
        to_delete=True,
        to_delete_timestamp=time.time() + datetime.timedelta(minutes=2).total_seconds(),
    )


async def good_mo_handler(tg_client: TGClient, update: Update):
    if update.message is None:
        return
    storage = Storage()
    await storage.tasks.put("good_mo")
    await tg_client.write_tg(
        "done",
        replay_message_id=update.message.id,
        to_delete=True,
        to_delete_timestamp=time.time() + datetime.timedelta(minutes=2).total_seconds(),
    )


async def wc_off_handler(tg_client: TGClient, update: Update):
    if update.message is None:
        return
    storage = Storage()
    await storage.tasks.put("wc_off")
    await tg_client.write_tg(
        "done",
        replay_message_id=update.message.id,
        to_delete=True,
        to_delete_timestamp=time.time() + datetime.timedelta(minutes=2).total_seconds(),
    )


async def balcony_off_handler(tg_client: TGClient, update: Update):
    if update.message is None:
        return
    storage = Storage()
    await storage.tasks.put("balcony_off")
    await tg_client.write_tg(
        "done",
        replay_message_id=update.message.id,
        to_delete=True,
        to_delete_timestamp=time.time() + datetime.timedelta(minutes=2).total_seconds(),
    )


async def exit_off_handler(tg_client: TGClient, update: Update):
    if update.message is None:
        return
    storage = Storage()
    await storage.tasks.put("exit_off")
    await tg_client.write_tg(
        "done",
        replay_message_id=update.message.id,
        to_delete=True,
        to_delete_timestamp=time.time() + datetime.timedelta(minutes=2).total_seconds(),
    )


async def evening_handler(tg_client: TGClient, update: Update):
    if update.message is None:
        return
    storage = Storage()
    await storage.tasks.put("evening")
    await tg_client.write_tg(
        "done",
        replay_message_id=update.message.id,
        to_delete=True,
        to_delete_timestamp=time.time() + datetime.timedelta(minutes=2).total_seconds(),
    )


async def paint_handler(tg_client: TGClient, update: Update):
    if update.message is None:
        return
    storage = Storage()
    await storage.tasks.put("paint")
    await tg_client.write_tg(
        "done",
        replay_message_id=update.message.id,
        to_delete=True,
        to_delete_timestamp=time.time() + datetime.timedelta(minutes=2).total_seconds(),
    )


async def clear_log_handler(tg_client: TGClient, update: Update):
    if update.message is None:
        return
    storage = Storage()
    await tg_client.write_tg_document("./storage/main.log")
    storage.put(SysSKeys.clear_log, True)
    await tg_client.write_tg(
        "done",
        replay_message_id=update.message.id,
        to_delete=True,
        to_delete_timestamp=time.time() + 2,
    )
    sys.exit(0)


def get_commands():
    return [
        ("b1", "Button one click"),
        ("b3", "Button long press"),
        ("quarantine", "Get quarantine"),
        ("skip_alarm", "Skip alarm"),
        ("water_done", "Water in cleaner"),
        ("restart", "Restart"),
        ("stats", "Quarantine stats"),
        ("minimize_lights", "Set max brightness"),
        ("20", "20 lines of logs"),
        ("b2", "Button double click"),
        ("pause", "Pause"),
        ("start", "Start"),
        ("remove_alarm", "Remove alarm"),
        ("50d", "50 lines of logs with debug"),
        ("log", "log file"),
        ("storage", "storage file"),
        ("clear_log", "clear log file"),
        ("sleep", "sleep"),
        ("good_mo", "good_mo"),
        ("wc_off", "wc_off"),
        ("balcony_off", "balcony_off"),
        ("exit_off", "exit_off"),
        ("evening", "evening"),
        ("paint", "paint"),
    ]


def get_handlers():
    return [
        (r"^/restart$", restart_handler),
        (r"^/pause$", pause_handler),
        (r"^/start$", start_handler),
        (r"^/quarantine$", get_quarantine_handler),
        (r"^/stats$", get_stats_handler),
        (r"^/minimize_lights$", minimize_lights_handler),
        (r"^/b1$", b1_lights_handler),
        (r"^/b2$", b2_lights_handler),
        (r"^/b3$", b3_lights_handler),
        (r"^/remove_alarm$", remove_alarm_lights_handler),
        (r"^/water_done$", water_done_handler),
        (r"^/log$", log_file_handler),
        (r"^/storage$", storage_file_handler),
        (r"^/skip_alarm$", skip_alarm_handler),
        (r"^\d\d:\d\d$", alarm_handler),
        (r"^/sleep$", sleep_handler),
        (r"^/good_mo$", good_mo_handler),
        (r"^/wc_off$", wc_off_handler),
        (r"^/balcony_off$", balcony_off_handler),
        (r"^/exit_off$", exit_off_handler),
        (r"^/evening$", evening_handler),
        (r"^/paint$", paint_handler),
        (r"^/clear_log$", clear_log_handler),
        (r"^\/?\d*d?$", log_lines_handler),
    ]
