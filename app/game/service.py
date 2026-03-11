from __future__ import annotations

import random
import re
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from app.store.database.models import GameStatus

if TYPE_CHECKING:
    from app.store.database.models import Game, Player
    from app.web.app import Application

STARTER_WORDS = [
    "апельсин",
    "банан",
    "дерево",
    "елка",
    "жираф",
    "зебра",
    "ирис",
    "кактус",
    "лимон",
    "медведь",
]

# Буквы на которые не начинают слова
SKIP_LETTERS = {"ь", "ъ", "й"}


class GameService:
    def __init__(self, app: Application):
        self.app = app

    @property
    def accessor(self):
        return self.app.store.game

    @property
    def _turn_timeout(self) -> int:
        return self.app.config.get("game", {}).get("turn_timeout", 60)

    @property
    def _vote_timeout(self) -> int:
        return self.app.config.get("game", {}).get("vote_timeout", 30)

    # ── Команды ───────────────────────────────────────────────────────

    async def start_game(self, chat_id: int) -> Game | None:
        """Создаёт новую игру. Возвращает None если игра уже идёт."""
        existing = await self.accessor.get_active_game(chat_id)
        if existing:
            return None
        return await self.accessor.create_game(chat_id)

    async def join_game(
        self,
        chat_id: int,
        user_id: int,
        first_name: str,
        username: str | None,
    ) -> tuple[Game | None, bool]:
        """Добавляет игрока в игру. Возвращает (game, already_joined)."""
        game = await self.accessor.get_active_game(chat_id)
        if not game or game.status != GameStatus.WAITING:
            return None, False

        existing = await self.accessor.get_player(game.id, user_id)
        if existing:
            return game, True

        await self.accessor.create_player(
            game.id, user_id, first_name, username
        )
        return game, False

    async def begin_game(self, chat_id: int) -> tuple[Game, Player] | None:
        """Запускает игру. Возвращает (game, first_player) или None."""
        game = await self.accessor.get_active_game(chat_id)
        if not game or game.status != GameStatus.WAITING:
            return None

        players = await self.accessor.get_active_players(game.id)
        if len(players) < 2:
            return None

        # Перемешиваем порядок игроков
        random.shuffle(players)
        for i, player in enumerate(players):
            player.turn_order = i
            await self.accessor.update_player(player)

        # Выбираем стартовое слово
        first_word = random.choice(STARTER_WORDS)

        # Добавляем стартовое слово в использованные
        await self.accessor.add_used_word(game.id, first_word, 0)

        # Обновляем игру
        game.status = GameStatus.IN_GAME
        game.current_word = first_word
        game.current_player_id = players[0].user_id
        game.turn_deadline = datetime.now(UTC) + timedelta(
            seconds=self._turn_timeout
        )
        game = await self.accessor.update_game(game)

        return game, players[0]

    # ── Игровой процесс ───────────────────────────────────────────────

    async def submit_word(self, chat_id: int, user_id: int, word: str) -> dict:
        """Обрабатывает слово от игрока. Возвращает dict с результатом."""
        game = await self.accessor.get_active_game(chat_id)

        if not game or game.status != GameStatus.IN_GAME:
            return {"ok": False, "reason": "not_your_turn"}

        if game.current_player_id != user_id:
            return {"ok": False, "reason": "not_your_turn"}

        word = word.strip().lower()

        # Проверяем формат
        if not re.fullmatch(r"[а-яёА-ЯЁ]+", word):
            return {"ok": False, "reason": "invalid_format"}

        # Проверяем первую букву
        required = self._get_required_letter(game.current_word)
        if word[0] != required:
            return {
                "ok": False,
                "reason": "wrong_letter",
                "required": required,
            }

        # Проверяем что слово не использовалось
        used = await self.accessor.get_used_words(game.id)
        if word in used:
            return {"ok": False, "reason": "already_used"}

        # Всё ок — переходим к голосованию
        game.status = GameStatus.VOTING
        game.pending_word = word
        game.pending_player_id = user_id
        game.vote_deadline = datetime.now(UTC) + timedelta(
            seconds=self._vote_timeout
        )
        await self.accessor.update_game(game)

        player = await self.accessor.get_player(game.id, user_id)
        return {"ok": True, "player": player}

    async def cast_vote(
        self, chat_id: int, voter_id: int, approve: bool
    ) -> dict:
        """Принимает голос от игрока."""
        game = await self.accessor.get_active_game(chat_id)
        if not game or game.status != GameStatus.VOTING:
            return {"ok": False, "reason": "no_voting"}

        # Нельзя голосовать за своё слово
        if game.pending_player_id == voter_id:
            return {"ok": False, "reason": "own_word"}

        # Проверяем что ещё не голосовал
        votes = await self.accessor.get_votes(game.id, game.pending_word)
        if any(v.voter_user_id == voter_id for v in votes):
            return {"ok": False, "reason": "already_voted"}

        await self.accessor.add_vote(
            game.id, game.pending_word, voter_id, approve
        )
        return {"ok": True}

    async def resolve_vote(self, chat_id: int) -> dict:
        """Подводит итог голосования. Вызывается по таймауту."""
        game = await self.accessor.get_active_game(chat_id)
        if not game or game.status != GameStatus.VOTING:
            return {"ok": False}

        players = await self.accessor.get_active_players(game.id)
        total_voters = len(players) - 1  # все кроме того кто сказал слово
        votes = await self.accessor.get_votes(game.id, game.pending_word)
        approvals = sum(1 for v in votes if v.approve)

        # Принято если больше 50% проголосовали за
        accepted = total_voters == 0 or (approvals / total_voters > 0.5)

        if accepted:
            # Начисляем очки и добавляем слово
            player = await self.accessor.get_player(
                game.id, game.pending_player_id
            )
            player.score += len(game.pending_word)
            await self.accessor.update_player(player)
            await self.accessor.add_used_word(
                game.id, game.pending_word, game.pending_player_id
            )
            game.current_word = game.pending_word
        else:
            # Слово отклонено — игрок выбывает
            player = await self.accessor.get_player(
                game.id, game.pending_player_id
            )
            player.is_active = False
            player.eliminated_at = datetime.now(UTC)
            await self.accessor.update_player(player)

        game.pending_word = None
        game.pending_player_id = None

        # Проверяем остался ли один игрок
        active_players = await self.accessor.get_active_players(game.id)
        if len(active_players) <= 1:
            return await self._finish_game(
                game,
                active_players,
                accepted=accepted,
                eliminated_player=(player if not accepted else None),
            )

        # Переходим к следующему игроку
        eliminated_order = player.turn_order if not accepted else None
        next_player = self._get_next_player(
            active_players, game.current_player_id, eliminated_order
        )
        game.status = GameStatus.IN_GAME
        game.current_player_id = next_player.user_id
        game.turn_deadline = datetime.now(UTC) + timedelta(
            seconds=self._turn_timeout
        )
        await self.accessor.update_game(game)

        result: dict = {
            "ok": True,
            "accepted": accepted,
            "approvals": approvals,
            "total": total_voters,
            "next_player": next_player,
            "winner": None,
            "remaining_count": len(active_players),
        }
        if not accepted:
            result["eliminated_player"] = player
        return result

    async def eliminate_on_timeout(self, chat_id: int) -> dict:
        """Выбивает игрока по таймауту хода."""
        game = await self.accessor.get_active_game(chat_id)
        if not game or game.status != GameStatus.IN_GAME:
            return {"ok": False}

        player = await self.accessor.get_player(game.id, game.current_player_id)
        player.is_active = False
        player.eliminated_at = datetime.now(UTC)
        await self.accessor.update_player(player)

        active_players = await self.accessor.get_active_players(game.id)
        if len(active_players) <= 1:
            return await self._finish_game(game, active_players)

        next_player = self._get_next_player(
            active_players, game.current_player_id, player.turn_order
        )
        game.current_player_id = next_player.user_id
        game.status = GameStatus.IN_GAME
        game.turn_deadline = datetime.now(UTC) + timedelta(
            seconds=self._turn_timeout
        )
        await self.accessor.update_game(game)

        return {
            "ok": True,
            "eliminated": player,
            "next_player": next_player,
            "winner": None,
            "remaining_count": len(active_players),
        }

    async def stop_game(self, chat_id: int) -> dict:
        """Досрочно завершает игру."""
        game = await self.accessor.get_active_game(chat_id)
        if not game:
            return {"ok": False}

        game.status = GameStatus.FINISHED
        game.finished_at = datetime.now(UTC)
        await self.accessor.update_game(game)

        scoreboard = await self.accessor.get_scoreboard(game.id)
        return {"ok": True, "scoreboard": scoreboard}

    # ── Вспомогательные методы ────────────────────────────────────────

    async def _finish_game(
        self,
        game: Game,
        active_players: list,
        accepted: bool = True,
        eliminated_player=None,
    ) -> dict:
        """Завершает игру."""
        game.status = GameStatus.FINISHED
        game.finished_at = datetime.now(UTC)
        await self.accessor.update_game(game)

        scoreboard = await self.accessor.get_scoreboard(game.id)
        winner = active_players[0] if active_players else None
        result: dict = {
            "ok": True,
            "accepted": accepted,
            "winner": winner,
            "scoreboard": scoreboard,
        }
        if eliminated_player is not None:
            result["eliminated_player"] = eliminated_player
        return result

    def _get_required_letter(self, word: str) -> str:
        """Возвращает букву с которой должно начинаться следующее слово."""
        for ch in reversed(word):
            if ch not in SKIP_LETTERS:
                return ch
        return word[-1]

    def _get_next_player(
        self,
        players: list,
        current_user_id: int,
        eliminated_turn_order: int | None = None,
    ) -> Player:
        """Возвращает следующего игрока по кругу.

        Если current_user_id уже не в списке (был выбыт), ищет первого
        игрока с turn_order > eliminated_turn_order, иначе — первого по кругу.
        players должен быть отсортирован по turn_order.
        """
        for i, p in enumerate(players):
            if p.user_id == current_user_id:
                return players[(i + 1) % len(players)]
        # Игрок выбыл — ищем следующего по turn_order
        if eliminated_turn_order is not None:
            for p in players:  # уже отсортированы по turn_order
                if p.turn_order > eliminated_turn_order:
                    return p
        return players[0]
