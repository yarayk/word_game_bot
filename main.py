from aiohttp.web import run_app

from app.web.app import setup_app

if __name__ == "__main__":
    application = setup_app(config_path="etc/config.yaml")
    run_app(
        application,
        host=application.config["web"]["host"],
        port=application.config["web"]["port"],
    )