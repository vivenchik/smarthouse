import aiofiles
from aiohttp import web

from example.configuration.config import get_config
from example.configuration.device_set import DeviceSet
from example.configuration.storage_keys import SKeys
from smarthouse.storage import Storage

routes = web.RouteTableDef()


@routes.get("/health")
async def health(request: web.Request):
    return web.Response(body={})


@routes.get("/logs")
async def logs(request: web.Request):
    config = get_config()
    if config.auth != request.headers.get("AuthorizationI"):
        raise web.HTTPForbidden()

    async with aiofiles.open("./storage/main.log", mode="rt") as f:
        content = await f.read()
    return web.Response(body=content)


@routes.post("/sleep")
async def sleep(request: web.Request):
    config = get_config()
    if config.auth != request.headers.get("AuthorizationI"):
        raise web.HTTPForbidden()

    storage = Storage()
    ds = DeviceSet()

    await storage.tasks.put("sleep")

    water_level = await ds.humidifier_new.water_level(proceeded_last=True)
    low_water_level = water_level < 30

    return web.Response(body={"response": "Мало воды в увлажнителе!" if low_water_level else None})


@routes.post("/good_mo")
async def good_mo(request: web.Request):
    config = get_config()
    if config.auth != request.headers.get("AuthorizationI"):
        raise web.HTTPForbidden()

    storage = Storage()
    await storage.tasks.put("good_mo")

    return web.Response(body={})


@routes.post("/wc_off")
async def wc_off(request: web.Request):
    config = get_config()
    if config.auth != request.headers.get("AuthorizationI"):
        raise web.HTTPForbidden()

    storage = Storage()
    await storage.tasks.put("wc_off")

    return web.Response(body={})


@routes.post("/balcony_off")
async def balcony_off(request: web.Request):
    config = get_config()
    if config.auth != request.headers.get("AuthorizationI"):
        raise web.HTTPForbidden()

    storage = Storage()
    await storage.tasks.put("balcony_off")

    return web.Response(body={})


@routes.post("/exit_off")
async def exit_off(request: web.Request):
    config = get_config()
    if config.auth != request.headers.get("AuthorizationI"):
        raise web.HTTPForbidden()

    storage = Storage()
    await storage.tasks.put("exit_off")

    return web.Response(body={})


@routes.post("/minimize_lights")
async def minimize_lights(request: web.Request):
    config = get_config()
    if config.auth != request.headers.get("AuthorizationI"):
        raise web.HTTPForbidden()

    storage = Storage()
    storage.put(SKeys.max_brightness, 0.4)

    return web.Response(body={})


@routes.post("/evening")
async def evening(request: web.Request):
    config = get_config()
    if config.auth != request.headers.get("AuthorizationI"):
        raise web.HTTPForbidden()

    storage = Storage()
    storage.put(SKeys.evening, not storage.get(SKeys.evening, True))
    await storage.tasks.put("evening")

    return web.Response(body={})


@routes.post("/paint")
async def paint(request: web.Request):
    config = get_config()
    if config.auth != request.headers.get("AuthorizationI"):
        raise web.HTTPForbidden()

    storage = Storage()
    await storage.tasks.put("paint")

    return web.Response(body={})
