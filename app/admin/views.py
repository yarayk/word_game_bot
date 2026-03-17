from __future__ import annotations

import logging
from dataclasses import asdict
from pathlib import Path

import aiohttp
from aiohttp import web

from app.admin.schema import (
    GameDetailSchema,
    GameSchema,
    PlayerSchema,
    StatsSchema,
    TopPlayerSchema,
)

logger = logging.getLogger(__name__)

_TEMPLATES_DIR = Path(__file__).parent.parent.parent / "templates"
_ADMIN_STOP_MSG = (
    "🛑 Игра была остановлена администратором.\n"
    "Вы можете начать новую игру с помощью /start_game!"
)


def _render(name: str) -> str:
    return (_TEMPLATES_DIR / name).read_text(encoding="utf-8")


def admin_index(request: web.Request) -> web.Response:
    return web.Response(
        text=_render("admin_index.html"), content_type="text/html"
    )


def admin_page(request: web.Request) -> web.Response:
    return web.Response(text=_render("stats.html"), content_type="text/html")


def _player_schema(p) -> PlayerSchema:
    return PlayerSchema(
        id=p.id,
        user_id=p.user_id,
        first_name=p.first_name,
        username=p.username,
        score=p.score,
        is_active=p.is_active,
        turn_order=p.turn_order,
    )


class GameListView(web.View):
    async def get(self) -> web.Response:
        page = max(1, int(self.request.query.get("page", 1)))
        per_page = min(100, max(1, int(self.request.query.get("per_page", 20))))
        offset = (page - 1) * per_page

        rows, total = await self.request.app.store.game.get_all_games(
            offset, per_page
        )
        games = [
            GameSchema(
                id=game.id,
                chat_id=game.chat_id,
                status=game.status.value,
                current_word=game.current_word,
                created_at=game.created_at.isoformat()
                if game.created_at
                else None,
                finished_at=game.finished_at.isoformat()
                if game.finished_at
                else None,
                players_count=players_count,
            )
            for game, players_count in rows
        ]
        return web.json_response(
            {
                "games": [asdict(g) for g in games],
                "total": total,
                "page": page,
                "per_page": per_page,
            }
        )


class GameDetailView(web.View):
    async def get(self) -> web.Response:
        game_id = int(self.request.match_info["id"])
        game = await self.request.app.store.game.get_game_by_id(game_id)
        if game is None:
            raise web.HTTPNotFound(text="Game not found")

        players = await self.request.app.store.game.get_all_players(game_id)
        used_words = await self.request.app.store.game.get_used_words_list(
            game_id
        )

        detail = GameDetailSchema(
            id=game.id,
            chat_id=game.chat_id,
            status=game.status.value,
            current_word=game.current_word,
            created_at=game.created_at.isoformat() if game.created_at else None,
            finished_at=game.finished_at.isoformat()
            if game.finished_at
            else None,
            players=[_player_schema(p) for p in players],
            used_words=used_words,
        )
        return web.json_response(asdict(detail))


class StatsView(web.View):
    async def get(self) -> web.Response:
        stats = await self.request.app.store.game.get_global_stats()
        schema = StatsSchema(
            total_games=stats["total_games"],
            finished_games=stats["finished_games"],
            active_games=stats["active_games"],
            total_words=stats["total_words"],
            top_players=[TopPlayerSchema(**p) for p in stats["top_players"]],
        )
        return web.json_response(asdict(schema))


def stop_games_page(request: web.Request) -> web.Response:
    return web.Response(
        text=_render("stop_games.html"), content_type="text/html"
    )


class BroadcastView(web.View):
    async def get(self) -> web.Response:
        return web.Response(
            text=_render("broadcast.html"), content_type="text/html"
        )

    async def post(self) -> web.Response:
        data = await self.request.json()
        text = (data.get("text") or "").strip()
        if not text:
            return web.json_response(
                {"ok": False, "reason": "empty_message"}, status=400
            )

        chat_ids = await self.request.app.store.game.get_all_chat_ids()
        if not chat_ids:
            return web.json_response({"ok": True, "sent": 0, "failed": 0})

        sent = 0
        failed = 0
        for chat_id in chat_ids:
            try:
                await self.request.app.store.tg_client.send_message(
                    chat_id=chat_id, text=text
                )
                sent += 1
            except aiohttp.ClientError as err:
                logger.warning("Broadcast failed for chat %d: %s", chat_id, err)
                failed += 1

        return web.json_response({"ok": True, "sent": sent, "failed": failed})


class GamesStopAllView(web.View):
    async def post(self) -> web.Response:
        active_games = await self.request.app.store.game.get_all_active_games()
        if not active_games:
            return web.json_response({"ok": True, "stopped": 0})

        stopped = 0
        for game in active_games:
            result = await self.request.app.store.game_service.stop_game(
                game.chat_id
            )
            if result["ok"]:
                stopped += 1
                await self.request.app.store.tg_client.send_message(
                    chat_id=game.chat_id, text=_ADMIN_STOP_MSG
                )

        return web.json_response({"ok": True, "stopped": stopped})


class GameStopView(web.View):
    async def post(self) -> web.Response:
        game_id = int(self.request.match_info["id"])
        game = await self.request.app.store.game.get_game_by_id(game_id)
        if game is None:
            raise web.HTTPNotFound(text="Game not found")

        result = await self.request.app.store.game_service.stop_game(
            game.chat_id
        )
        if not result["ok"]:
            return web.json_response(
                {"ok": False, "reason": "no_active_game"}, status=400
            )

        await self.request.app.store.tg_client.send_message(
            chat_id=game.chat_id, text=_ADMIN_STOP_MSG
        )

        return web.json_response(
            {
                "ok": True,
                "scoreboard": [
                    asdict(_player_schema(p)) for p in result["scoreboard"]
                ],
            }
        )
