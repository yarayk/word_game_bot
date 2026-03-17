from aiohttp.web_app import Application

__all__ = ("register_urls",)


def register_urls(application: Application):
    """Регистрирует URL-адреса, связанные с пользователями, в приложении.

    Args:
        application: Экземпляр приложения aiohttp.
    """
