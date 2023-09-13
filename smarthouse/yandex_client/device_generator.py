from smarthouse.yandex_client.client import YandexClient


async def generate():
    ya_client = YandexClient()
    info = await ya_client.info()
    for device in info["devices"]:
        if device["type"] == "devices.types.sensor.motion":
            print(f"MotionSensor(\"{device['id']}\", \"{device['name']}\")")
