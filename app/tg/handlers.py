from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.store.database.models import GameStatus
from app.tg.dataclasses import CallbackQuery, Update

if TYPE_CHECKING:
    from app.web.app import Application

logger = logging.getLogger(__name__)

_VOTE_KEYBOARD = {
    "inline_keyboard": [
        [
            {"text": "✅ Да", "callback_data": "vote:yes"},
            {"text": "❌ Нет", "callback_data": "vote:no"},
        ]
    ]
}

_LOBBY_KEYBOARD = {
    "inline_keyboard": [
        [
            {"text": "🙋 Присоединиться", "callback_data": "lobby:join"},
            {"text": "▶️ Начать игру", "callback_data": "lobby:begin"},
        ]
    ]
}


def _build_lobby_text(players: list) -> str:
    if not players:
        player_list = "— никого пока нет"
    else:
        player_list = "\n".join(f"• {p.first_name}" for p in players)
    return (
        "🎮 Игра в Слова!\n\n"
        f"Игроки ({len(players)}):\n"
        f"{player_list}\n\n"
        "Нажми кнопку чтобы присоединиться!"
    )


async def handle_update(update: Update, app: Application) -> None:
    if update.callback_query is not None:
        cq = update.callback_query
        if cq.data.startswith("vote:"):
            await handle_vote_callback(cq, app)
        elif cq.data.startswith("lobby:"):
            await handle_lobby_callback(cq, app)
        return

    if update.message is not None:
        await _handle_message(update.message, app)


async def _handle_message(message, app: Application) -> None:
    logger.debug("handle_update: text=%s", message.text)

    chat_id = message.chat.id

    if any(m.is_bot for m in message.new_chat_members):
        await handle_bot_added(chat_id, app)
        return

    user_id = message.from_.id
    first_name = message.from_.first_name
    username = message.from_.username
    text = message.text

    if text is None:
        return

    if message.chat.type == "private" and text.startswith("/"):
        await app.store.tg_client.send_message(
            chat_id,
            "❌ Игра доступна только в групповых чатах. Добавь меня в группу!",
        )
        return

    await _route_command(chat_id, user_id, first_name, username, text, app)


async def _route_command(
    chat_id: int,
    user_id: int,
    first_name: str,
    username: str | None,
    text: str,
    app: Application,
) -> None:
    if text.startswith("/start_game"):
        await handle_start_game(chat_id, app)
    elif text.startswith("/join"):
        await handle_join(chat_id, user_id, first_name, username, app)
    elif text.startswith("/begin"):
        await handle_begin(chat_id, user_id, app)
    elif text.startswith("/stop_game"):
        await handle_stop_game(chat_id, app)
    elif text.startswith("/game_info"):
        await handle_game_info(chat_id, app)
    elif text.startswith("/help"):
        await handle_help(chat_id, app)
    elif not text.startswith("/"):
        await handle_word(chat_id, user_id, text, app)


async def handle_help(chat_id: int, app: Application) -> None:
    await app.store.tg_client.send_message(
        chat_id,
        "📖 Правила игры в Слова:\n"
        "Игроки по очереди называют слова. Каждое следующее слово должно "
        "начинаться на последнюю букву предыдущего. Другие игроки голосуют "
        "— существует ли названное слово. Кто не успел назвать слово или "
        "назвал несуществующее — выбывает. Побеждает последний оставшийся!\n\n"
        "📋 Команды:\n"
        "/start_game — начать новую игру\n"
        "/join — присоединиться к игре\n"
        "/begin — запустить игру (нужно ≥ 2 игрока)\n"
        "/stop_game — досрочно завершить игру\n"
        "/game_info — информация о текущей игре\n"
        "/help — показать эту справку",
    )


async def handle_bot_added(chat_id: int, app: Application) -> None:
    await app.store.tg_client.send_message(
        chat_id,
        "👋 Привет! Я бот для игры в Слова.\n\n"
        "📖 Правила:\n"
        "Игроки по очереди называют слова. Каждое следующее слово должно "
        "начинаться на последнюю букву предыдущего. Другие игроки голосуют "
        "— существует ли названное слово. Кто не успел назвать слово или "
        "назвал несуществующее — выбывает. Побеждает последний оставшийся!\n\n"
        "📋 Команды:\n"
        "/start_game — начать новую игру\n"
        "/join — присоединиться к игре\n"
        "/begin — запустить игру (нужно ≥ 2 игрока)\n"
        "/stop_game — досрочно завершить игру\n"
        "/game_info — информация о текущей игре\n"
        "/help — показать эту справку",
    )


async def handle_start_game(chat_id: int, app: Application) -> None:
    game = await app.store.game_service.start_game(chat_id)
    if game is None:
        await app.store.tg_client.send_message(
            chat_id,
            "⚠️ Игра уже идёт! Используй /game_info для деталей.",
        )
        return

    message_id = await app.store.tg_client.send_message(
        chat_id, _build_lobby_text([]), _LOBBY_KEYBOARD
    )
    if message_id:
        game.lobby_message_id = message_id
        await app.store.game.update_game(game)


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
        if not game.lobby_message_id:
            await app.store.tg_client.send_message(
                chat_id, f"{first_name}, ты уже в игре!"
            )
        return

    players = await app.store.game.get_active_players(game.id)
    if game.lobby_message_id:
        await app.store.tg_client.edit_message_text(
            chat_id,
            game.lobby_message_id,
            _build_lobby_text(players),
            reply_markup=_LOBBY_KEYBOARD,
        )
    else:
        await app.store.tg_client.send_message(
            chat_id,
            f"✅ {first_name} присоединился!\nИгроков: {len(players)}",
        )


async def handle_begin(chat_id: int, user_id: int, app: Application) -> None:
    game = await app.store.game.get_active_game(chat_id)
    if game is None:
        await app.store.tg_client.send_message(
            chat_id,
            "Нельзя начать игру. "
            "Нужно минимум 2 игрока и открытая игра (/start_game).",
        )
        return

    player = await app.store.game.get_player(game.id, user_id)
    if player is None:
        await app.store.tg_client.send_message(
            chat_id,
            "❌ Только участники игры могут её начать. Сначала нажми /join.",
        )
        return

    lobby_message_id = game.lobby_message_id
    result = await app.store.game_service.begin_game(chat_id)

    if result is None:
        await app.store.tg_client.send_message(
            chat_id,
            "Нельзя начать игру. "
            "Нужно минимум 2 игрока и открытая игра (/start_game).",
        )
        return

    await _send_game_started(chat_id, result, lobby_message_id, app)


async def handle_lobby_callback(
    callback_query: CallbackQuery, app: Application
) -> None:
    chat_id = callback_query.message.chat.id
    action = callback_query.data.split(":", 1)[1]

    if action == "join":
        user_id = callback_query.from_.id
        first_name = callback_query.from_.first_name
        username = callback_query.from_.username

        game, already_joined = await app.store.game_service.join_game(
            chat_id, user_id, first_name, username
        )

        if game is None:
            await app.store.tg_client.answer_callback_query(
                callback_query.id,
                text="Нет открытой игры.",
                show_alert=True,
            )
            return

        if already_joined:
            await app.store.tg_client.answer_callback_query(
                callback_query.id,
                text="Ты уже в игре!",
                show_alert=True,
            )
            return

        await app.store.tg_client.answer_callback_query(callback_query.id)

        players = await app.store.game.get_active_players(game.id)
        if game.lobby_message_id:
            await app.store.tg_client.edit_message_text(
                chat_id,
                game.lobby_message_id,
                _build_lobby_text(players),
                reply_markup=_LOBBY_KEYBOARD,
            )

    elif action == "begin":
        game = await app.store.game.get_active_game(chat_id)
        if game is None or game.status != GameStatus.WAITING:
            await app.store.tg_client.answer_callback_query(
                callback_query.id,
                text="Нет открытой игры.",
                show_alert=True,
            )
            return

        requester_id = callback_query.from_.id
        requester = await app.store.game.get_player(game.id, requester_id)
        if requester is None:
            await app.store.tg_client.answer_callback_query(
                callback_query.id,
                text="Только участники игры могут её начать.",
                show_alert=True,
            )
            return

        players = await app.store.game.get_active_players(game.id)
        if len(players) < 2:
            await app.store.tg_client.answer_callback_query(
                callback_query.id,
                text="Нужно минимум 2 игрока!",
                show_alert=True,
            )
            return

        await app.store.tg_client.answer_callback_query(callback_query.id)

        lobby_message_id = game.lobby_message_id
        result = await app.store.game_service.begin_game(chat_id)
        if result is not None:
            await _send_game_started(chat_id, result, lobby_message_id, app)


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
            game = await app.store.game.get_active_game(chat_id)
            if game and game.status == GameStatus.IN_GAME:
                player = await app.store.game.get_player(game.id, user_id)
                if player and player.is_active:
                    current = await app.store.game.get_player(
                        game.id, game.current_player_id
                    )
                    name = current.first_name if current else "другой игрок"
                    await app.store.tg_client.send_message(
                        chat_id, f"⏳ Сейчас ходит {name}."
                    )
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
    players = await app.store.game.get_active_players(game.id)
    total_voters = len(players) - 1

    vote_text = (
        f"🗳 {player.first_name} называет слово: {game.pending_word}\n"
        f"Голосуйте — существует ли это слово?\n"
        f"Проголосовало: 0 из {total_voters}"
    )
    message_id = await app.store.tg_client.send_message(
        chat_id, vote_text, _VOTE_KEYBOARD
    )
    if message_id:
        game.vote_message_id = message_id
        await app.store.game.update_game(game)

    app.store.timer.start_vote_timer(chat_id)


async def handle_vote_callback(
    callback_query: CallbackQuery, app: Application
) -> None:
    chat_id = callback_query.message.chat.id
    voter_id = callback_query.from_.id
    approve = callback_query.data == "vote:yes"

    result = await app.store.game_service.cast_vote(chat_id, voter_id, approve)

    if not result["ok"]:
        reason = result.get("reason")
        if reason == "own_word":
            alert = "Нельзя голосовать за своё слово."
        elif reason == "already_voted":
            alert = "Ты уже проголосовал."
        elif reason == "not_participant":
            alert = "Ты не участвуешь в этой игре."
        else:
            alert = None
        await app.store.tg_client.answer_callback_query(
            callback_query.id, text=alert, show_alert=bool(alert)
        )
        return

    await app.store.tg_client.answer_callback_query(callback_query.id)

    game = await app.store.game.get_active_game(chat_id)
    if game is None:
        return

    players = await app.store.game.get_active_players(game.id)
    votes = await app.store.game.get_votes(game.id, game.pending_word)
    total_voters = len(players) - 1

    if game.vote_message_id:
        await app.store.tg_client.edit_message_text(
            chat_id,
            game.vote_message_id,
            f"🗳 Слово: {game.pending_word}\n"
            f"Голосуйте — существует ли это слово?\n"
            f"Проголосовало: {len(votes)} из {total_voters}",
            reply_markup=_VOTE_KEYBOARD,
        )

    if len(votes) >= total_voters:
        vote_message_id = game.vote_message_id
        app.store.timer.cancel(chat_id)
        result = await app.store.game_service.resolve_vote(chat_id)
        await _send_vote_result(chat_id, result, app, vote_message_id)


async def _send_game_started(
    chat_id: int,
    result: tuple,
    lobby_message_id: int | None,
    app: Application,
) -> None:
    game, first_player = result
    required = app.store.game_service._get_required_letter(game.current_word)
    start_text = (
        f"🎮 Игра началась!\n\n"
        f"Первое слово: {game.current_word}\n"
        f"Ход: {first_player.first_name}\n"
        f"Назови слово на букву «{required}»"
    )
    if lobby_message_id:
        await app.store.tg_client.edit_message_text(
            chat_id, lobby_message_id, start_text
        )
    else:
        await app.store.tg_client.send_message(chat_id, start_text)
    app.store.timer.start_turn_timer(chat_id)


async def _send_vote_result(
    chat_id: int,
    result: dict,
    app: Application,
    vote_message_id: int | None = None,
) -> None:
    if not result["ok"]:
        return

    accepted = result.get("accepted")
    has_winner = bool(result.get("winner"))
    elim = result.get("eliminated_player")

    if not accepted and elim:
        if has_winner:
            winner = result["winner"]
            verdict = (
                f"Такого слова не существует.\n"
                f"❌ {elim.first_name} выбыл.\n"
                f"🏆 Победитель: {winner.first_name}!"
            )
        else:
            game = await app.store.game.get_active_game(chat_id)
            players = (
                await app.store.game.get_active_players(game.id) if game else []
            )
            names = ", ".join(p.first_name for p in players) or "—"
            verdict = (
                f"Такого слова не существует.\n"
                f"❌ {elim.first_name} выбыл.\n"
                f"Остались: {names}"
            )
    else:
        verdict = "✅ Слово принято!"

    if vote_message_id:
        await app.store.tg_client.edit_message_text(
            chat_id, vote_message_id, verdict
        )
    else:
        await app.store.tg_client.send_message(chat_id, verdict)

    if has_winner:
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
