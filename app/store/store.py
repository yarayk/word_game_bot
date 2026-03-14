from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.web.app import Application


class Store:
    def __init__(self, app: Application):
        from app.store.database.database import Database
        from app.tg.client import TgClient
        from app.tg.poller import Poller
        from app.users.accessor import UserAccessor

        self.user = UserAccessor(self)
        self.tg_client = TgClient(app)
        self.poller = Poller(app)
        self.database = Database(app)
