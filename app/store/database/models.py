from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class GameStatus(enum.Enum):
    WAITING = "waiting"
    IN_GAME = "in_game"
    VOTING = "voting"
    FINISHED = "finished"


class Game(Base):
    __tablename__ = "games"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    status: Mapped[GameStatus] = mapped_column(
        Enum(GameStatus), default=GameStatus.WAITING, nullable=False
    )
    current_word: Mapped[str | None] = mapped_column(String(100))
    current_player_id: Mapped[int | None] = mapped_column(BigInteger)
    pending_word: Mapped[str | None] = mapped_column(String(100))
    pending_player_id: Mapped[int | None] = mapped_column(BigInteger)
    turn_deadline: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    vote_deadline: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    vote_message_id: Mapped[int | None] = mapped_column(BigInteger)
    lobby_message_id: Mapped[int | None] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )

    players: Mapped[list[Player]] = relationship(back_populates="game")
    words: Mapped[list[UsedWord]] = relationship(back_populates="game")
    votes: Mapped[list[Vote]] = relationship(back_populates="game")


class Player(Base):
    __tablename__ = "players"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    first_name: Mapped[str] = mapped_column(String(100))
    username: Mapped[str | None] = mapped_column(String(100))
    score: Mapped[float] = mapped_column(Float, default=0.0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    turn_order: Mapped[int] = mapped_column(Integer, default=0)
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    eliminated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )

    game: Mapped[Game] = relationship(back_populates="players")


class UsedWord(Base):
    __tablename__ = "used_words"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id"), nullable=False)
    word: Mapped[str] = mapped_column(String(100), nullable=False)
    player_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    used_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    game: Mapped[Game] = relationship(back_populates="words")


class Vote(Base):
    __tablename__ = "votes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id"), nullable=False)
    word: Mapped[str] = mapped_column(String(100), nullable=False)
    voter_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    approve: Mapped[bool] = mapped_column(Boolean, nullable=False)
    voted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    game: Mapped[Game] = relationship(back_populates="votes")


class BotState(Base):
    """Singleton-строка (id=1) для хранения состояния бота между рестартами."""

    __tablename__ = "bot_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    tg_offset: Mapped[int] = mapped_column(BigInteger, default=0)
