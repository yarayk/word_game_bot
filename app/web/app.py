from aiohttp.web import (
    Application as AiohttpApplication,
)

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
    setup_routes(app)
    return app
