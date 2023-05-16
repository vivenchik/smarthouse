from aiohttp import web

from example.configuration.config import get_config
from example.configuration.storage_keys import SKeys
from smarthouse.storage import Storage

routes = web.RouteTableDef()


@routes.get("/health")
async def health(request: web.Request):
    return web.Response()


@routes.post("/sleep")
async def sleep(request: web.Request):
    config = get_config()
    if config.auth != request.headers.get("Authorization"):
        raise web.HTTPForbidden()

    storage = Storage()
    await storage.tasks.put("sleep")

    return web.Response()


@routes.post("/good_mo")
async def good_mo(request: web.Request):
    config = get_config()
    if config.auth != request.headers.get("Authorization"):
        raise web.HTTPForbidden()

    storage = Storage()
    await storage.tasks.put("good_mo")

    return web.Response()


@routes.post("/wc_off")
async def wc_off(request: web.Request):
    config = get_config()
    if config.auth != request.headers.get("Authorization"):
        raise web.HTTPForbidden()

    storage = Storage()
    await storage.tasks.put("wc_off")

    return web.Response()


@routes.post("/balcony_off")
async def balcony_off(request: web.Request):
    config = get_config()
    if config.auth != request.headers.get("Authorization"):
        raise web.HTTPForbidden()

    storage = Storage()
    await storage.tasks.put("balcony_off")

    return web.Response()


@routes.post("/exit_off")
async def exit_off(request: web.Request):
    config = get_config()
    if config.auth != request.headers.get("Authorization"):
        raise web.HTTPForbidden()

    storage = Storage()
    await storage.tasks.put("exit_off")

    return web.Response()


@routes.post("/humidifier")
async def humidifier(request: web.Request):
    config = get_config()
    if config.auth != request.headers.get("Authorization"):
        raise web.HTTPForbidden()

    storage = Storage()
    await storage.tasks.put("humidifier")

    return web.Response()


@routes.post("/minimize_lights")
async def minimize_lights(request: web.Request):
    config = get_config()
    if config.auth != request.headers.get("Authorization"):
        raise web.HTTPForbidden()

    storage = Storage()
    storage.put(SKeys.max_brightness, 0.4)

    return web.Response()


@routes.post("/evening")
async def evening(request: web.Request):
    config = get_config()
    if config.auth != request.headers.get("Authorization"):
        raise web.HTTPForbidden()

    storage = Storage()
    storage.put(SKeys.evening, not storage.get(SKeys.evening, True))
    await storage.tasks.put("evening")

    return web.Response()


@routes.post("/paint")
async def paint(request: web.Request):
    config = get_config()
    if config.auth != request.headers.get("Authorization"):
        raise web.HTTPForbidden()

    storage = Storage()
    await storage.tasks.put("paint")

    return web.Response()
