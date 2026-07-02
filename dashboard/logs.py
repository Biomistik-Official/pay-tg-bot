"""
Чтение и live-стриминг лог-файлов бота.

Логи лежат как logs/bot_YYYY-MM-DD.log. Для live-режима следим
за самым свежим файлом (на смене суток он поменяется).
"""

from __future__ import annotations

import asyncio
import os
import re
from datetime import datetime
from pathlib import Path

LOGS_DIR = Path("logs")
_FILE_RE = re.compile(r"^bot_(\d{4}-\d{2}-\d{2})\.log$")


def _log_files_sorted() -> list[Path]:
    if not LOGS_DIR.exists():
        return []
    files = []
    for p in LOGS_DIR.iterdir():
        if p.is_file() and _FILE_RE.match(p.name):
            files.append(p)
    files.sort(key=lambda p: p.name)
    return files


def latest_log_file() -> Path | None:
    files = _log_files_sorted()
    return files[-1] if files else None


def tail_lines(n: int = 300) -> list[str]:
    """Вернуть последние n строк, при необходимости выбирая из предыдущих файлов."""
    files = _log_files_sorted()
    collected: list[str] = []
    for path in reversed(files):
        try:
            with path.open("r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
        except FileNotFoundError:
            continue
        collected = lines + collected
        if len(collected) >= n:
            break
    return [ln.rstrip("\n") for ln in collected[-n:]]


async def stream_lines():
    """
    Асинхронный генератор новых строк. Раз в 500мс проверяет размер
    самого свежего файла и, если он вырос, отдаёт новые строки.
    """
    current: Path | None = latest_log_file()
    offset = current.stat().st_size if current and current.exists() else 0

    while True:
        await asyncio.sleep(0.5)
        latest = latest_log_file()
        if latest is None:
            continue

        if current is None or latest != current:
            current = latest
            offset = 0

        try:
            size = current.stat().st_size
        except FileNotFoundError:
            continue

        if size < offset:
            offset = 0

        if size == offset:
            continue

        try:
            with current.open("r", encoding="utf-8", errors="replace") as f:
                f.seek(offset)
                chunk = f.read()
                offset = f.tell()
        except FileNotFoundError:
            continue

        for line in chunk.splitlines():
            if line.strip():
                yield line


def list_log_days() -> list[str]:
    days = []
    for p in _log_files_sorted():
        m = _FILE_RE.match(p.name)
        if m:
            days.append(m.group(1))
    return days


def read_day(day: str) -> list[str]:
    path = LOGS_DIR / f"bot_{day}.log"
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", errors="replace") as f:
        return [ln.rstrip("\n") for ln in f.readlines()]
