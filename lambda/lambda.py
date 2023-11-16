import logging
import os
import time
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)


def request(path):
    for _ in range(5):
        try:
            url = os.environ.get("HOME_URL")
            password = os.environ.get("HOME_PASSWORD")
            httprequest = Request(f"{url}/{path}", headers={"AuthorizationI": password}, method="POST")
            with urlopen(httprequest) as response:
                if response.status == 200:
                    return 0
                logger.error(response.status)
            time.sleep(2)
        except Exception as exc:
            logger.exception(exc)
            time.sleep(2)
    return 1


def handler(event, context):
    result = None
    resp = "готово"
    if (
        "request" in event
        and "original_utterance" in event["request"]
        and len(event["request"]["original_utterance"]) > 0
    ):
        if event["request"]["original_utterance"] == "спать":
            resp = "спокойной"
            result = request("sleep")
        if event["request"]["original_utterance"] == "доброе утро":
            resp = "доброе!"
            result = request("good_mo")
        if event["request"]["original_utterance"] == "убавь свет":
            result = request("minimize_lights")
        if event["request"]["original_utterance"] == "туалет":
            result = request("wc_off")
        if event["request"]["original_utterance"] == "балкон":
            result = request("balcony_off")
        if event["request"]["original_utterance"] == "коридор":
            result = request("exit_off")
        if event["request"]["original_utterance"] == "вечер":
            resp = "сейчас"
            result = request("evening")
        if event["request"]["original_utterance"] == "рисование":
            resp = "жги"
            result = request("paint")

    if result != 0:
        logger.error(event["request"]["original_utterance"])
        resp = "ошибка"

    response = {
        "version": event["version"],
        "session": event["session"],
        "response": {"text": resp, "end_session": "true"},
    }

    return response
