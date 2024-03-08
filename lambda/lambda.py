import json
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
                    json_response = json.loads(response.read().decode("utf-8"))
                    return json_response.get("response")
                logger.error(response.status)
            time.sleep(2)
        except Exception as exc:
            logger.exception(exc)
            time.sleep(2)
    return "ошибка"


def handler(event, context):
    api_response = None
    default_resp = "готово"
    if (
        "request" in event
        and "original_utterance" in event["request"]
        and len(event["request"]["original_utterance"]) > 0
    ):
        if event["request"]["original_utterance"] == "спать":
            default_resp = "спокойной"
            api_response = request("sleep")
        if event["request"]["original_utterance"] == "доброе утро":
            default_resp = "Доброе!"
            api_response = request("good_mo")
        if event["request"]["original_utterance"] == "убавь свет":
            api_response = request("minimize_lights")
        if event["request"]["original_utterance"] == "туалет":
            api_response = request("wc_off")
        if event["request"]["original_utterance"] == "балкон":
            api_response = request("balcony_off")
        if event["request"]["original_utterance"] == "коридор":
            api_response = request("exit_off")
        if event["request"]["original_utterance"] == "вечер":
            default_resp = "сейчас"
            api_response = request("evening")
        if event["request"]["original_utterance"] == "рисование":
            default_resp = "жги"
            api_response = request("paint")
        if event["request"]["original_utterance"] == "свечка":
            api_response = request("air_cleaner_off")
        if event["request"]["original_utterance"] == "голос макс":
            api_response = request("voice_max")
        if event["request"]["original_utterance"] == "голос мини":
            api_response = request("voice_min")

    if api_response == "ошибка":
        logger.error(event["request"]["original_utterance"])

    response = {
        "version": event["version"],
        "session": event["session"],
        "response": {"text": api_response or default_resp, "end_session": "true"},
    }

    return response
