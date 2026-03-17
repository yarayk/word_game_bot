from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import func, select
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

    async def get_all_active_games(self) -> list[Game]:
        """Возвращает все незавершённые игры (по всем чатам)."""
        async with self.get_session() as session:
            result = await session.execute(
                select(Game).where(Game.status != GameStatus.FINISHED)
            )
            return list(result.scalars().all())

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
            session.add(
                UsedWord(
                    game_id=game_id,
                    word=word,
                    player_user_id=player_user_id,
                )
            )
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
            session.add(
                Vote(
                    game_id=game_id,
                    word=word,
                    voter_user_id=voter_user_id,
                    approve=approve,
                )
            )
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

    # ── Admin API ──────────────────────────────────────────────────────

    async def get_game_by_id(self, game_id: int) -> Game | None:
        """Возвращает игру по первичному ключу."""
        async with self.get_session() as session:
            return await session.get(Game, game_id)

    async def get_all_games(
        self, offset: int = 0, limit: int = 20
    ) -> tuple[list[tuple[Game, int]], int]:
        """Возвращает пагинированный список игр с количеством игроков."""
        player_count_subq = (
            select(func.count(Player.id))
            .where(Player.game_id == Game.id)
            .correlate(Game)
            .scalar_subquery()
        )
        async with self.get_session() as session:
            total = await session.scalar(select(func.count(Game.id)))
            result = await session.execute(
                select(Game, player_count_subq.label("players_count"))
                .order_by(Game.created_at.desc())
                .offset(offset)
                .limit(limit)
            )
            rows = [(row.Game, row.players_count) for row in result.all()]
        return rows, total or 0

    async def get_all_players(self, game_id: int) -> list[Player]:
        """Возвращает всех игроков игры (включая выбывших)."""
        async with self.get_session() as session:
            result = await session.execute(
                select(Player)
                .where(Player.game_id == game_id)
                .order_by(Player.turn_order)
            )
            return list(result.scalars().all())

    async def get_used_words_list(self, game_id: int) -> list[str]:
        """Возвращает список использованных слов в порядке добавления."""
        async with self.get_session() as session:
            result = await session.execute(
                select(UsedWord.word)
                .where(UsedWord.game_id == game_id)
                .order_by(UsedWord.used_at)
            )
            return list(result.scalars().all())

    async def get_global_stats(self) -> dict:
        """Возвращает агрегированную статистику по всем играм."""
        async with self.get_session() as session:
            total_games = await session.scalar(select(func.count(Game.id))) or 0
            finished_games = await session.scalar(
                select(func.count(Game.id)).where(
                    Game.status == GameStatus.FINISHED
                )
            ) or 0
            active_games = await session.scalar(
                select(func.count(Game.id)).where(
                    Game.status != GameStatus.FINISHED
                )
            ) or 0
            total_words = (
                await session.scalar(select(func.count(UsedWord.id))) or 0
            )
            top_result = await session.execute(
                select(
                    Player.user_id,
                    Player.first_name,
                    func.sum(Player.score).label("total_score"),
                )
                .group_by(Player.user_id, Player.first_name)
                .order_by(func.sum(Player.score).desc())
                .limit(10)
            )
            top_players = [
                {
                    "user_id": row.user_id,
                    "first_name": row.first_name,
                    "total_score": row.total_score or 0.0,
                }
                for row in top_result.all()
            ]
        return {
            "total_games": total_games,
            "finished_games": finished_games,
            "active_games": active_games,
            "total_words": total_words,
            "top_players": top_players,
        }
