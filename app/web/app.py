import yaml
from aiohttp.web import Application as AiohttpApplication

from app.store.store import Store

from .routes import setup_routes

__all__ = ("Application",)


class Application(AiohttpApplication):
    config = None
    store = None
    database = None


app = Application()


def setup_app(config_path: str) -> Application:
    with open(config_path) as f:
        app.config = yaml.safe_load(f)

    app.store = Store(app)

    setup_routes(app)

    app.on_startup.append(_on_startup)
    app.on_cleanup.append(_on_cleanup)

    return app


async def _on_startup(application: Application) -> None:
    await application.store.database.connect()
    await application.store.poller.start()
    await application.store.timer.restore_timers()


async def _on_cleanup(application: Application) -> None:
    application.store.timer.stop()
    await application.store.poller.stop()
    await application.store.database.disconnect()
