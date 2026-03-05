from aiohttp import web
from aiohttp.abc import Request


@web.middleware
async def example_mw(request: Request, handler):
    return await handler(request)
