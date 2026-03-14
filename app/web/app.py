import yaml
from aiohttp.web import Application as AiohttpApplication

from app.store.store import Store

from .routes import setup_routes

__all__ = ("Application",)


class Application(AiohttpApplication):
    """Основной класс приложения для веб-сервера word game.

    Наследуется от класса Application aiohttp и добавляет атрибуты
    конфигурации, хранилища и базы данных.
    """

    config = None
    store = None
    database = None


app = Application()


def setup_app(config_path: str) -> Application:
    """Настраивает приложение с маршрутами и конфигурацией.

    Args:
        config_path: Путь к файлу конфигурации.

    Returns:
        Application: Настроенный экземпляр приложения.
    """
    # Загружаем конфиг
    with open(config_path) as f:
        app.config = yaml.safe_load(f)

    # Создаём store
        app.store = Store(app)

    # Регистрируем маршруты
    setup_routes(app)

    # Хуки запуска и остановки
    app.on_startup.append(_on_startup)
    app.on_cleanup.append(_on_cleanup)

    return app


async def _on_startup(application: Application) -> None:
    await application.store.poller.start()


async def _on_cleanup(application: Application) -> None:
    await application.store.poller.stop()