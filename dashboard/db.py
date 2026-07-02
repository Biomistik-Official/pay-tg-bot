"""
Read-only обёртка над SQLite базой бота.

Все запросы открывают соединение в режиме ?mode=ro, чтобы дашборд
физически не мог что-то испортить, даже при ошибке.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterable

from bot.config import config


def _db_uri() -> str:
    path = Path(config.database_path).resolve().as_posix()
    return f"file:{path}?mode=ro"


@contextmanager
def ro_conn():
    conn = sqlite3.connect(_db_uri(), uri=True, timeout=5.0)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def query_all(sql: str, params: Iterable[Any] = ()) -> list[dict]:
    with ro_conn() as conn:
        rows = conn.execute(sql, tuple(params)).fetchall()
        return [dict(r) for r in rows]


def query_one(sql: str, params: Iterable[Any] = ()) -> dict | None:
    with ro_conn() as conn:
        row = conn.execute(sql, tuple(params)).fetchone()
        return dict(row) if row else None


def query_scalar(sql: str, params: Iterable[Any] = ()) -> Any:
    with ro_conn() as conn:
        row = conn.execute(sql, tuple(params)).fetchone()
        return row[0] if row else None
