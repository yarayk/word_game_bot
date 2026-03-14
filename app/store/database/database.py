from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

if TYPE_CHECKING:
    from app.web.app import Application


class Database:
    def __init__(self, app: Application):
        self.app = app
        self._engine = None
        self._session_maker = None

    async def connect(self) -> None:
        self._engine = create_async_engine(
            self.app.config["store"]["database_url"],
            echo=True,  # выводит все SQL запросы в консоль
        )
        self._session_maker = async_sessionmaker(
            self._engine,
            expire_on_commit=False,
        )

    async def disconnect(self) -> None:
        if self._engine:
            await self._engine.dispose()

    def get_session(self) -> AsyncSession:
        return self._session_maker()
