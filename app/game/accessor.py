from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.store.database.models import Game, GameStatus, Player, UsedWord, Vote

if TYPE_CHECKING:
    from app.web.app import Application


class GameAccessor:
    def __init__(self, app: Application):
        self.app = app

    def get_session(self) -> AsyncSession:
        return self.app.store.database.get_session()

    # ── Игры ──────────────────────────────────────────────────────────

    async def get_active_game(self, chat_id: int) -> Game | None:
        """Возвращает активную игру в чате (не завершённую)."""
        async with self.get_session() as session:
            result = await session.execute(
                select(Game).where(
                    Game.chat_id == chat_id,
                    Game.status != GameStatus.FINISHED,
                )
            )
            return result.scalar_one_or_none()

    async def create_game(self, chat_id: int) -> Game:
        """Создаёт новую игру в чате."""
        async with self.get_session() as session:
            game = Game(chat_id=chat_id, status=GameStatus.WAITING)
            session.add(game)
            await session.commit()
            await session.refresh(game)
            return game

    async def update_game(self, game: Game) -> Game:
        """Сохраняет изменения игры."""
        async with self.get_session() as session:
            merged = await session.merge(game)
            await session.commit()
            await session.refresh(merged)
            return merged

    # ── Игроки ────────────────────────────────────────────────────────

    async def get_player(self, game_id: int, user_id: int) -> Player | None:
        """Возвращает игрока по game_id и user_id."""
        async with self.get_session() as session:
            result = await session.execute(
                select(Player).where(
                    Player.game_id == game_id,
                    Player.user_id == user_id,
                )
            )
            return result.scalar_one_or_none()

    async def get_active_players(self, game_id: int) -> list[Player]:
        """Возвращает список активных игроков."""
        async with self.get_session() as session:
            result = await session.execute(
                select(Player)
                .where(Player.game_id == game_id, Player.is_active)
                .order_by(Player.turn_order)
            )
            return list(result.scalars().all())

    async def create_player(
        self, game_id: int, user_id: int, first_name: str, username: str | None
    ) -> Player:
        """Добавляет игрока в игру."""
        async with self.get_session() as session:
            players = await self.get_active_players(game_id)
            player = Player(
                game_id=game_id,
                user_id=user_id,
                first_name=first_name,
                username=username,
                turn_order=len(players),
            )
            session.add(player)
            await session.commit()
            await session.refresh(player)
            return player

    async def update_player(self, player: Player) -> Player:
        """Сохраняет изменения игрока."""
        async with self.get_session() as session:
            merged = await session.merge(player)
            await session.commit()
            await session.refresh(merged)
            return merged

    # ── Слова ─────────────────────────────────────────────────────────

    async def get_used_words(self, game_id: int) -> set[str]:
        """Возвращает множество использованных слов."""
        async with self.get_session() as session:
            result = await session.execute(
                select(UsedWord.word).where(UsedWord.game_id == game_id)
            )
            return set(result.scalars().all())

    async def add_used_word(
        self, game_id: int, word: str, player_user_id: int
    ) -> None:
        """Добавляет слово в список использованных."""
        async with self.get_session() as session:
            session.add(UsedWord(
                game_id=game_id,
                word=word,
                player_user_id=player_user_id,
            ))
            await session.commit()

    # ── Голоса ────────────────────────────────────────────────────────

    async def get_votes(self, game_id: int, word: str) -> list[Vote]:
        """Возвращает все голоса за слово."""
        async with self.get_session() as session:
            result = await session.execute(
                select(Vote).where(
                    Vote.game_id == game_id,
                    Vote.word == word,
                )
            )
            return list(result.scalars().all())

    async def add_vote(
        self, game_id: int, word: str, voter_user_id: int, approve: bool
    ) -> None:
        """Добавляет голос."""
        async with self.get_session() as session:
            session.add(Vote(
                game_id=game_id,
                word=word,
                voter_user_id=voter_user_id,
                approve=approve,
            ))
            await session.commit()

    async def get_scoreboard(self, game_id: int) -> list[Player]:
        """Возвращает игроков отсортированных по очкам."""
        async with self.get_session() as session:
            result = await session.execute(
                select(Player)
                .where(Player.game_id == game_id)
                .order_by(Player.score.desc())
            )
            return list(result.scalars().all())