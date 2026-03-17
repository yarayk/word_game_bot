from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PlayerSchema:
    id: int
    user_id: int
    first_name: str
    username: str | None
    score: float
    is_active: bool
    turn_order: int


@dataclass
class GameSchema:
    id: int
    chat_id: int
    status: str
    current_word: str | None
    created_at: str | None
    finished_at: str | None
    players_count: int


@dataclass
class GameDetailSchema:
    id: int
    chat_id: int
    status: str
    current_word: str | None
    created_at: str | None
    finished_at: str | None
    players: list[PlayerSchema]
    used_words: list[str]


@dataclass
class TopPlayerSchema:
    user_id: int
    first_name: str
    total_score: float


@dataclass
class StatsSchema:
    total_games: int
    finished_games: int
    active_games: int
    total_words: int
    top_players: list[TopPlayerSchema]
