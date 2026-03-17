from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from aiohttp import ClientSession

from app.tg.dataclasses import Update

if TYPE_CHECKING:
    from app.web.app import Application

logger = logging.getLogger(__name__)


class TgClient:
    def __init__(self, app: Application):
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

    async def get_updates(
        self, offset: int = 0, request_timeout: int = 30
    ) -> list[Update]:
        async with self._session.get(
            f"{self.api_url}/getUpdates",
            params={"offset": offset, "timeout": request_timeout},
        ) as resp:
            data = await resp.json()
            if not data.get("ok"):
                logger.error("getUpdates failed: %s", data)
                return []
            return [Update.from_dict(u) for u in data["result"]]

    async def send_message(
        self,
        chat_id: int,
        text: str,
        reply_markup: dict | None = None,
    ) -> int | None:
        payload: dict = {"chat_id": chat_id, "text": text}
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup
        async with self._session.post(
            f"{self.api_url}/sendMessage",
            json=payload,
        ) as resp:
            data = await resp.json()
            if not data.get("ok"):
                logger.error("sendMessage failed: %s", data)
                return None
            return data["result"]["message_id"]

    async def answer_callback_query(
        self,
        callback_query_id: str,
        text: str | None = None,
        show_alert: bool = False,
    ) -> None:
        payload: dict = {"callback_query_id": callback_query_id}
        if text is not None:
            payload["text"] = text
        if show_alert:
            payload["show_alert"] = show_alert
        async with self._session.post(
            f"{self.api_url}/answerCallbackQuery",
            json=payload,
        ) as resp:
            data = await resp.json()
            if not data.get("ok"):
                logger.error("answerCallbackQuery failed: %s", data)

    async def edit_message_text(
        self,
        chat_id: int,
        message_id: int,
        text: str,
        reply_markup: dict | None = None,
    ) -> None:
        payload: dict = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text,
        }
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup
        async with self._session.post(
            f"{self.api_url}/editMessageText",
            json=payload,
        ) as resp:
            data = await resp.json()
            if not data.get("ok"):
                logger.error("editMessageText failed: %s", data)
