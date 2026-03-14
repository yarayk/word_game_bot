from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from app.store.database.models import GameStatus

if TYPE_CHECKING:
    from app.web.app import Application

logger = logging.getLogger(__name__)

_DEFAULT_TURN_TIMEOUT = 60
_DEFAULT_VOTE_TIMEOUT = 30


class TimerManager:
    def __init__(self, app: Application):
        self.app = app
        self._timers: dict[int, asyncio.Task] = {}

    @property
    def turn_timeout(self) -> int:
        return self.app.config.get("game", {}).get(
            "turn_timeout", _DEFAULT_TURN_TIMEOUT
        )

    @property
    def vote_timeout(self) -> int:
        return self.app.config.get("game", {}).get(
            "vote_timeout", _DEFAULT_VOTE_TIMEOUT
        )

    def cancel(self, chat_id: int) -> None:
        if task := self._timers.pop(chat_id, None):
            task.cancel()

    def start_turn_timer(
        self, chat_id: int, delay: float | None = None
    ) -> None:
        self.cancel(chat_id)
        self._timers[chat_id] = asyncio.create_task(
            self._turn_timeout(
                chat_id, delay if delay is not None else self.turn_timeout
            )
        )

    def start_vote_timer(
        self, chat_id: int, delay: float | None = None
    ) -> None:
        self.cancel(chat_id)
        self._timers[chat_id] = asyncio.create_task(
            self._vote_timeout(
                chat_id, delay if delay is not None else self.vote_timeout
            )
        )

    def stop(self) -> None:
        for task in self._timers.values():
            task.cancel()
        self._timers.clear()

    async def restore_timers(self) -> None:
        """Восстанавливает таймеры после рестарта по дедлайнам из БД."""
        games = await self.app.store.game.get_all_active_games()
        now = datetime.now(UTC)

        for game in games:
            if game.status == GameStatus.IN_GAME and game.turn_deadline:
                remaining = (game.turn_deadline - now).total_seconds()
                self.start_turn_timer(game.chat_id, delay=max(remaining, 0))
            elif game.status == GameStatus.VOTING and game.vote_deadline:
                remaining = (game.vote_deadline - now).total_seconds()
                self.start_vote_timer(game.chat_id, delay=max(remaining, 0))

        logger.info("Restored %d timers", len(self._timers))

    # ── Внутренние обработчики ─────────────────────────────────────────

    async def _turn_timeout(self, chat_id: int, delay: float) -> None:
        await asyncio.sleep(delay)
        try:
            result = await self.app.store.game_service.eliminate_on_timeout(
                chat_id
            )
        except Exception:
            logger.exception("Turn timeout error for chat %d", chat_id)
            return

        if not result["ok"]:
            return

        eliminated = result.get("eliminated")
        if eliminated:
            await self.app.store.tg_client.send_message(
                chat_id,
                f"⏰ {eliminated.first_name} не успел назвать слово"
                " и выбывает.",
            )

        if result.get("winner"):
            winner = result["winner"]
            await self.app.store.tg_client.send_message(
                chat_id,
                f"🏆 Победитель: {winner.first_name}!\n\n"
                + _format_scoreboard(result["scoreboard"]),
            )
        elif result.get("next_player"):
            next_player = result["next_player"]
            game = await self.app.store.game.get_active_game(chat_id)
            required = self.app.store.game_service._get_required_letter(
                game.current_word
            )
            await self.app.store.tg_client.send_message(
                chat_id,
                f"Ход: {next_player.first_name}\n"
                f"Назови слово на букву «{required}»",
            )
            self.start_turn_timer(chat_id)

    async def _vote_timeout(self, chat_id: int, delay: float) -> None:
        await asyncio.sleep(delay)
        try:
            result = await self.app.store.game_service.resolve_vote(chat_id)
        except Exception:
            logger.exception("Vote timeout error for chat %d", chat_id)
            return

        if not result["ok"]:
            return

        accepted = result.get("accepted")
        verdict = "⏰ Время голосования вышло! " + (
            "✅ Слово принято!" if accepted else "❌ Слово отклонено!"
        )
        await self.app.store.tg_client.send_message(chat_id, verdict)

        if result.get("winner"):
            winner = result["winner"]
            await self.app.store.tg_client.send_message(
                chat_id,
                f"🏆 Победитель: {winner.first_name}!\n\n"
                + _format_scoreboard(result["scoreboard"]),
            )
        elif result.get("next_player"):
            next_player = result["next_player"]
            game = await self.app.store.game.get_active_game(chat_id)
            required = self.app.store.game_service._get_required_letter(
                game.current_word
            )
            await self.app.store.tg_client.send_message(
                chat_id,
                f"Ход: {next_player.first_name}\n"
                f"Назови слово на букву «{required}»",
            )
            self.start_turn_timer(chat_id)


def _format_scoreboard(players) -> str:
    if not players:
        return "Нет результатов."

    lines = ["🏆 Результаты:"]
    medals = ["🥇", "🥈", "🥉"]

    for i, player in enumerate(players):
        medal = medals[i] if i < 3 else f"{i + 1}."
        lines.append(f"{medal} {player.first_name} — {int(player.score)} очков")

    return "\n".join(lines)
