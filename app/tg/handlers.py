from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.tg.dataclasses import Update

if TYPE_CHECKING:
    from app.web.app import Application

logger = logging.getLogger(__name__)


async def handle_update(update: Update, app: Application) -> None:
    if update.message is None:
        return

    logger.debug("handle_update: text=%s", update.message.text)

    message = update.message
    chat_id = message.chat.id
    user_id = message.from_.id
    first_name = message.from_.first_name
    username = message.from_.username
    text = message.text

    if text is None:
        return

    if text.startswith("/start_game"):
        await handle_start_game(chat_id, app)
    elif text.startswith("/join"):
        await handle_join(chat_id, user_id, first_name, username, app)
    elif text.startswith("/begin"):
        await handle_begin(chat_id, app)
    elif text.startswith("/stop_game"):
        await handle_stop_game(chat_id, app)
    elif text.startswith("/game_info"):
        await handle_game_info(chat_id, app)
    elif text in ("+", "-"):
        await handle_vote(chat_id, user_id, text == "+", app)
    elif not text.startswith("/"):
        await handle_word(chat_id, user_id, text, app)


async def handle_start_game(chat_id: int, app: Application) -> None:
    game = await app.store.game_service.start_game(chat_id)
    if game is None:
        await app.store.tg_client.send_message(
            chat_id,
            "⚠️ Игра уже идёт! Используй /game_info для деталей.",
        )
        return

    await app.store.tg_client.send_message(
        chat_id,
        "🎮 Новая игра в Слова!\n\n"
        "Присоединяйтесь командой /join\n"
        "Когда все готовы — /begin",
    )


async def handle_join(
    chat_id: int,
    user_id: int,
    first_name: str,
    username: str | None,
    app: Application,
) -> None:
    game, already_joined = await app.store.game_service.join_game(
        chat_id, user_id, first_name, username
    )

    if game is None:
        await app.store.tg_client.send_message(
            chat_id,
            "Нет открытой игры. Начни новую: /start_game",
        )
        return

    if already_joined:
        await app.store.tg_client.send_message(
            chat_id,
            f"{first_name}, ты уже в игре!",
        )
        return

    players = await app.store.game.get_active_players(game.id)
    await app.store.tg_client.send_message(
        chat_id,
        f"✅ {first_name} присоединился!\nИгроков: {len(players)}",
    )


async def handle_begin(chat_id: int, app: Application) -> None:
    result = await app.store.game_service.begin_game(chat_id)

    if result is None:
        await app.store.tg_client.send_message(
            chat_id,
            "Нельзя начать игру. "
            "Нужно минимум 2 игрока и открытая игра (/start_game).",
        )
        return

    game, first_player = result
    required = app.store.game_service._get_required_letter(game.current_word)

    await app.store.tg_client.send_message(
        chat_id,
        f"🎮 Игра началась!\n\n"
        f"Первое слово: {game.current_word}\n"
        f"Ход: {first_player.first_name}\n"
        f"Назови слово на букву «{required}»",
    )
    app.store.timer.start_turn_timer(chat_id)


async def handle_stop_game(chat_id: int, app: Application) -> None:
    app.store.timer.cancel(chat_id)
    result = await app.store.game_service.stop_game(chat_id)

    if not result["ok"]:
        await app.store.tg_client.send_message(
            chat_id,
            "Нет активной игры.",
        )
        return

    await app.store.tg_client.send_message(
        chat_id,
        "🛑 Игра остановлена досрочно.\n\n"
        + _format_scoreboard(result["scoreboard"]),
    )


async def handle_game_info(chat_id: int, app: Application) -> None:
    game = await app.store.game.get_active_game(chat_id)

    if game is None:
        await app.store.tg_client.send_message(
            chat_id,
            "Нет активной игры. Начни: /start_game",
        )
        return

    players = await app.store.game.get_active_players(game.id)
    used = await app.store.game.get_used_words(game.id)

    await app.store.tg_client.send_message(
        chat_id,
        f"📊 Статус игры\n\n"
        f"Статус: {game.status.value}\n"
        f"Текущее слово: {game.current_word or '—'}\n"
        f"Слов сыграно: {len(used)}\n"
        f"Активных игроков: {len(players)}",
    )


async def handle_word(
    chat_id: int, user_id: int, word: str, app: Application
) -> None:
    logger.debug(
        "handle_word: chat_id=%s user_id=%s word=%s", chat_id, user_id, word
    )
    result = await app.store.game_service.submit_word(chat_id, user_id, word)
    logger.debug("submit_word result: %s", result)

    if not result["ok"]:
        reason = result["reason"]

        if reason == "not_your_turn":
            return

        if reason == "wrong_letter":
            required = result["required"]
            await app.store.tg_client.send_message(
                chat_id,
                f"❌ Слово должно начинаться на букву «{required}»!",
            )
        elif reason == "already_used":
            await app.store.tg_client.send_message(
                chat_id,
                "❌ Это слово уже было использовано!",
            )
        elif reason == "invalid_format":
            await app.store.tg_client.send_message(
                chat_id,
                "❌ Слово должно состоять только из русских букв.",
            )
        return

    player = result["player"]
    game = await app.store.game.get_active_game(chat_id)

    await app.store.tg_client.send_message(
        chat_id,
        f"🗳 {player.first_name} называет слово: {game.pending_word}\n"
        f"Голосуйте — существует ли это слово?\n"
        f"Напишите + или - в чат",
    )
    app.store.timer.start_vote_timer(chat_id)


async def handle_vote(
    chat_id: int, voter_id: int, approve: bool, app: Application
) -> None:
    result = await app.store.game_service.cast_vote(chat_id, voter_id, approve)

    if not result["ok"]:
        reason = result.get("reason")
        if reason == "no_voting":
            await app.store.tg_client.send_message(
                chat_id, "Голосование сейчас не идёт."
            )
        elif reason == "own_word":
            await app.store.tg_client.send_message(
                chat_id, "Нельзя голосовать за своё слово."
            )
        elif reason == "already_voted":
            await app.store.tg_client.send_message(
                chat_id, "Ты уже проголосовал."
            )
        return

    # Проверяем — все ли проголосовали
    game = await app.store.game.get_active_game(chat_id)
    if game is None:
        return

    players = await app.store.game.get_active_players(game.id)
    votes = await app.store.game.get_votes(game.id, game.pending_word)

    # Голосуют все кроме того кто назвал слово
    total_voters = len(players) - 1

    if len(votes) >= total_voters:
        # Все проголосовали — подводим итог
        result = await app.store.game_service.resolve_vote(chat_id)
        await _send_vote_result(chat_id, result, app)


async def _send_vote_result(
    chat_id: int, result: dict, app: Application
) -> None:
    if not result["ok"]:
        return

    accepted = result.get("accepted")
    verdict = "✅ Слово принято!" if accepted else "❌ Слово отклонено!"
    await app.store.tg_client.send_message(chat_id, verdict)

    if result.get("winner"):
        winner = result["winner"]
        await app.store.tg_client.send_message(
            chat_id,
            f"🏆 Победитель: {winner.first_name}!\n\n"
            + _format_scoreboard(result["scoreboard"]),
        )
        return

    next_player = result.get("next_player")
    if next_player:
        game = await app.store.game.get_active_game(chat_id)
        required = app.store.game_service._get_required_letter(
            game.current_word
        )
        await app.store.tg_client.send_message(
            chat_id,
            f"Ход: {next_player.first_name}\n"
            f"Назови слово на букву «{required}»",
        )
        app.store.timer.start_turn_timer(chat_id)


def _format_scoreboard(players) -> str:
    if not players:
        return "Нет результатов."

    lines = ["🏆 Результаты:"]
    medals = ["🥇", "🥈", "🥉"]

    for i, player in enumerate(players):
        medal = medals[i] if i < 3 else f"{i + 1}."
        lines.append(f"{medal} {player.first_name} — {int(player.score)} очков")

    return "\n".join(lines)
