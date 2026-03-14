import logging
from typing import TYPE_CHECKING

from aiohttp import ClientSession

from app.tg.dataclasses import Update

if TYPE_CHECKING:
    from app.web.app import Application

logger = logging.getLogger(__name__)


class TgClient:
    def __init__(self, app: "Application"):
        self.app = app
        self._session: ClientSession | None = None

    @property
    def token(self) -> str:
        return self.app.config["bot"]["token"]

    @property
    def api_url(self) -> str:
        return f"https://api.telegram.org/bot{self.token}"

    async def start(self) -> None:
        self._session = ClientSession()
        logger.info("TgClient started")

    async def stop(self) -> None:
        if self._session:
            await self._session.close()
        logger.info("TgClient stopped")

    async def get_updates(self, offset: int = 0) -> list[Update]:
        async with self._session.get(
            f"{self.api_url}/getUpdates",
            params={"offset": offset, "timeout": 30},
        ) as resp:
            data = await resp.json()
            if not data.get("ok"):
                logger.error("getUpdates failed: %s", data)
                return []
            return [Update.from_dict(u) for u in data["result"]]

    async def send_message(self, chat_id: int, text: str) -> None:
        async with self._session.post(
            f"{self.api_url}/sendMessage",
            json={"chat_id": chat_id, "text": text},
        ) as resp:
            data = await resp.json()
            if not data.get("ok"):
                logger.error("sendMessage failed: %s", data)