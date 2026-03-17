# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A Telegram bot implementing a Russian word chain game ("Слова"). Players take turns naming words where each word must start with the last valid letter of the previous word. Words are voted on by other players.

## Commands

**Linting and formatting:**
```sh
ruff format          # format code
ruff check --fix     # lint with auto-fix
ruff format --check && ruff check --no-fix  # CI check (no changes)
```

**Tests:**
```sh
pytest               # run all tests
pytest tests/test_foo.py::test_bar  # run a single test
```

**Database migrations (reads DB URL from `etc/config.yaml`):**
```sh
venv/Scripts/alembic upgrade head
venv/Scripts/alembic revision --autogenerate -m "description"
```

**Run the app:**
```sh
python -m aiohttp.web app.web.app:setup_app etc/config.yaml
```

## Architecture

### Dependency Container (`app/store/store.py`)

`Store` is the central dependency container instantiated at startup. All components hold a reference to `app` (the `Application`) and access siblings via `app.store.*`:
- `app.store.database` — DB connection and session factory
- `app.store.tg_client` — Telegram HTTP API client
- `app.store.poller` — long-polling background task
- `app.store.game` — `GameAccessor` (DB queries for game domain)
- `app.store.game_service` — `GameService` (game rules and state machine)
- `app.store.user` — `UserAccessor` (stub)

All imports in `Store.__init__` are deferred (inside the method body) to avoid circular imports.

### Telegram Layer (`app/tg/`)

- `client.py` — `TgClient`: wraps Telegram Bot API (`getUpdates`, `sendMessage`) using `aiohttp.ClientSession`
- `poller.py` — `Poller`: asyncio background task doing long-polling (offset tracking, calls `handle_update`)
- `handlers.py` — command routing and response formatting; calls `game_service` for logic and `tg_client` to reply
- `dataclasses.py` — `Update`, `Message`, `Chat`, `MessageFrom` parsed from Telegram JSON

### Game Layer (`app/game/`)

- `accessor.py` — `GameAccessor`: all raw DB queries (CRUD for `Game`, `Player`, `UsedWord`, `Vote`)
- `service.py` — `GameService`: game rules, state transitions, scoring; calls accessor for persistence

**Game state machine:** `WAITING` → `IN_GAME` → `VOTING` → `FINISHED`

**Game flow:**
1. `/start_game` — creates `Game(WAITING)`
2. `/join` — adds `Player` rows to the waiting game
3. `/begin` — shuffles turn order, picks random starter word, transitions to `IN_GAME`
4. Player submits a word → validated (letter rule, Russian-only regex, not reused) → `VOTING`
5. Others vote `+`/`-`; when all have voted `resolve_vote()` runs: accepted → score += word length, rejected → player eliminated
6. Last active player wins, or `/stop_game` ends early

### Database (`app/store/database/`)

- `database.py` — `Database`: creates async SQLAlchemy engine from `config["store"]["database_url"]`, provides `get_session()`
- `models.py` — SQLAlchemy ORM models: `Game`, `Player`, `UsedWord`, `Vote`; `GameStatus` enum

### Configuration

Config is loaded from a YAML file (default `etc/config.yaml`) at startup. Required keys:
```yaml
bot:
  token: "<telegram bot token>"
store:
  database_url: "postgresql+asyncpg://user:pass@host/dbname"
```
Alembic migrations also read `etc/config.yaml` directly (see `app/store/migrations/env.py`).

## Code Conventions

- **Accessor pattern**: DB queries live in `*Accessor` classes; business logic lives in `*Service` classes
- **Docstrings**: Google-style (`convention = "google"` in ruff config); Russian language is allowed in comments and docstrings
- **Imports**: deferred inside `__init__` methods to avoid circular imports (common in store.py, accessors)
- `TYPE_CHECKING` blocks used for type hints that would otherwise cause circular imports
- Service methods return plain `dict` with `{"ok": bool, ...}` for command results
