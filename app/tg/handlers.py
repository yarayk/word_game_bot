import logging
from typing import TYPE_CHECKING

from app.tg.dataclasses import Update

if TYPE_CHECKING:
    from app.web.app import Application

logger = logging.getLogger(__name__)


async def handle_update(update: Update, app: "Application") -> None:
    if update.message is None:
        return

    if update.message.text is None:
        return

    logger.info(
        "Message from %s in chat %s: %s",
        update.message.from_.first_name,
        update.message.chat.id,
        update.message.text,
    )

    await app.store.tg_client.send_message(
        chat_id=update.message.chat.id,
        text=update.message.text,
    )