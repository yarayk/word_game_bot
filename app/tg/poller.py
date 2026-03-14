from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from app.store.database.models import BotState
from app.tg.handlers import handle_update

if TYPE_CHECKING:
    from app.web.app import Application

logger = logging.getLogger(__name__)


class Poller:
    def __init__(self, app: Application):
        self.app = app
        self._task: asyncio.Task | None = None
        self._offset: int = 0

    async def start(self) -> None:
        await self.app.store.tg_client.start()
        self._offset = await self._load_offset()
        self._task = asyncio.create_task(self._poll())
        logger.info("Poller started (offset=%d)", self._offset)

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        await self._save_offset(self._offset)
        await self.app.store.tg_client.stop()
        logger.info("Poller stopped (offset=%d)", self._offset)

    async def _load_offset(self) -> int:
        async with self.app.store.database.get_session() as session:
            state = await session.get(BotState, 1)
            return state.tg_offset if state else 0

    async def _save_offset(self, offset: int) -> None:
        async with self.app.store.database.get_session() as session:
            state = BotState(id=1, tg_offset=offset)
            await session.merge(state)
            await session.commit()

    async def _poll(self) -> None:
        while True:
            try:
                updates = await self.app.store.tg_client.get_updates(
                    offset=self._offset,
                    request_timeout=30,
                )
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Polling error")
                await asyncio.sleep(1)
                continue

            for update in updates:
                self._offset = update.update_id + 1
                await self._save_offset(self._offset)
                try:
                    await self._handle_update(update)
                except asyncio.CancelledError:
                    raise
                except Exception:
                    logger.exception(
                        "Error handling update %d", update.update_id
                    )
                    if update.message:
                        try:
                            await self.app.store.tg_client.send_message(
                                update.message.chat.id,
                                "⚠️ Что-то пошло не так. Попробуй ещё раз.",
                            )
                        except Exception:
                            pass

    async def _handle_update(self, update) -> None:
        await handle_update(update, self.app)
