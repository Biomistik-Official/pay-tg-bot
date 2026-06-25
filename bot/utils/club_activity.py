"""
Проверка активности участников клубов Brawl Stars.
Логика адаптирована из club_checker/bot.py.
Определяет неактивных игроков по их логу боёв (3+ дня без боёв).
"""

import asyncio
import aiohttp
from datetime import datetime, timezone, timedelta
from typing import Optional

from bot.config import config
from bot.utils.logger import logger


# Порог неактивности в днях
INACTIVE_DAYS_THRESHOLD = 3

# Ограничение одновременных запросов к API
API_SEMAPHORE_LIMIT = 10

# Клубы для проверки (берём из brawlstars.py)
CLUB_TAGS = ["2UUQ0989V", "2CL9LRVCL", "2CP8R2Q8U"]

BS_API_BASE = "https://api.brawlstars.com/v1"


# ─── Вспомогательные функции ──────────────────────────────────────────────────

def _encode_tag(tag: str) -> str:
    """Кодирует тег для URL: добавляет %23 вместо #."""
    tag = tag.strip().lstrip("#")
    return f"%23{tag}"


def _parse_bs_timestamp(ts: str) -> datetime:
    """
    Парсит временную метку Brawl Stars формата '20250619T120000.000Z'
    в datetime с timezone UTC.
    """
    ts = ts.replace(".000Z", "Z")
    if ts.endswith("Z"):
        ts = ts[:-1]
    return datetime.strptime(ts, "%Y%m%dT%H%M%S").replace(tzinfo=timezone.utc)


def _translate_role(role: str) -> str:
    """Переводит роль участника на русский."""
    roles = {
        "president": "Президент",
        "vicePresident": "Вице-президент",
        "senior": "Старейшина",
        "member": "Участник",
    }
    return roles.get(role, role)


def _escape_html(text: str) -> str:
    """Экранирует спецсимволы HTML."""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


# ─── Запросы к API ────────────────────────────────────────────────────────────

async def _api_get(session: aiohttp.ClientSession, url: str) -> Optional[dict]:
    """Выполняет GET-запрос к Brawl Stars API."""
    headers = {"Authorization": f"Bearer {config.brawl_stars_api_token}"}
    try:
        async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status == 200:
                return await resp.json()
            elif resp.status == 404:
                logger.warning(f"[ClubActivity] Не найдено: {url}")
                return None
            elif resp.status == 429:
                logger.warning(f"[ClubActivity] Rate limit! URL: {url}")
                await asyncio.sleep(2)
                return None
            else:
                text = await resp.text()
                logger.error(f"[ClubActivity] Ошибка API {resp.status}: {text}")
                return None
    except Exception as e:
        logger.error(f"[ClubActivity] Ошибка запроса {url}: {e}")
        return None


async def _get_club_info(session: aiohttp.ClientSession, club_tag: str) -> Optional[dict]:
    """Получает информацию о клубе, включая список участников."""
    url = f"{BS_API_BASE}/clubs/{_encode_tag(club_tag)}"
    return await _api_get(session, url)


async def _get_player_battlelog(
    session: aiohttp.ClientSession,
    player_tag: str,
    semaphore: asyncio.Semaphore,
) -> Optional[list]:
    """Получает лог боёв игрока (с ограничением параллелизма)."""
    async with semaphore:
        url = f"{BS_API_BASE}/players/{_encode_tag(player_tag)}/battlelog"
        data = await _api_get(session, url)
        if data and "items" in data:
            return data["items"]
        return None


def _get_last_battle_time(battlelog: list) -> Optional[datetime]:
    """Возвращает время последнего боя из лога."""
    if not battlelog:
        return None
    first_battle = battlelog[0]
    ts = first_battle.get("battleTime")
    if ts:
        return _parse_bs_timestamp(ts)
    return None


def _split_message(text: str, max_len: int = 4000) -> list[str]:
    """Разбивает длинное сообщение на части по секциям."""
    if len(text) <= max_len:
        return [text]

    chunks = []
    current = ""
    sections = text.split("\n\n")

    for section in sections:
        if len(current) + len(section) + 2 > max_len:
            if current:
                chunks.append(current.strip())
            current = section
        else:
            current += "\n\n" + section if current else section

    if current:
        chunks.append(current.strip())

    return chunks if chunks else [text[:max_len]]


# ─── Основные функции проверки ────────────────────────────────────────────────

async def check_all_clubs_inactive() -> str:
    """
    Проверяет все клубы и возвращает HTML-отчёт со списком неактивных игроков
    (3+ дня без боёв).
    """
    now = datetime.now(timezone.utc)
    threshold = now - timedelta(days=INACTIVE_DAYS_THRESHOLD)
    semaphore = asyncio.Semaphore(API_SEMAPHORE_LIMIT)

    all_results = []

    async with aiohttp.ClientSession() as session:
        for club_tag in CLUB_TAGS:
            club_data = await _get_club_info(session, club_tag)
            if not club_data:
                all_results.append(f"❌ Клуб <code>#{club_tag}</code> — не удалось получить данные\n")
                continue

            club_name = _escape_html(club_data.get("name", f"#{club_tag}"))
            members = club_data.get("members", [])

            if not members:
                all_results.append(
                    f"📋 <b>{club_name}</b> (<code>#{club_tag}</code>)\n"
                    f"Участников не найдено.\n"
                )
                continue

            # Параллельно получаем логи боёв
            tasks = [
                _get_player_battlelog(session, member["tag"], semaphore)
                for member in members
            ]
            battlelogs = await asyncio.gather(*tasks)

            inactive_members = []

            for member, battlelog in zip(members, battlelogs):
                name = member.get("name", "???")
                tag = member.get("tag", "")
                role = member.get("role", "member")
                trophies = member.get("trophies", 0)

                if not battlelog:
                    inactive_members.append({
                        "name": name,
                        "tag": tag,
                        "role": _translate_role(role),
                        "trophies": trophies,
                        "last_battle": None,
                        "days_inactive": "∞",
                    })
                else:
                    last_time = _get_last_battle_time(battlelog)
                    if last_time and last_time < threshold:
                        days_ago = (now - last_time).days
                        inactive_members.append({
                            "name": name,
                            "tag": tag,
                            "role": _translate_role(role),
                            "trophies": trophies,
                            "last_battle": last_time,
                            "days_inactive": days_ago,
                        })

            # Сортируем: самые неактивные сверху
            inactive_members.sort(
                key=lambda x: x["days_inactive"] if isinstance(x["days_inactive"], int) else 9999,
                reverse=True,
            )

            header = (
                f"🏠 <b>{club_name}</b> (<code>#{club_tag}</code>)\n"
                f"👥 Участников: {len(members)} | "
                f"😴 Неактивных (3+ д): {len(inactive_members)}\n"
                f"{'─' * 28}\n"
            )

            if inactive_members:
                lines = []
                for i, m in enumerate(inactive_members, 1):
                    days_str = f"{m['days_inactive']}д" if isinstance(m["days_inactive"], int) else "нет боёв"
                    line = (
                        f"{i}. <b>{_escape_html(m['name'])}</b>\n"
                        f"   🏷 <code>{m['tag']}</code> | 🏆 {m['trophies']}\n"
                        f"   👤 {_escape_html(m['role'])} | ⏰ {days_str}\n"
                    )
                    lines.append(line)
                body = "\n".join(lines)
            else:
                body = "✅ Все участники активны!\n"

            all_results.append(header + body)

    if not all_results:
        return "Не удалось получить данные ни по одному клубу."

    final = (
        f"📊 <b>Отчёт о неактивных игроках</b>\n"
        f"📅 {now.strftime('%d.%m.%Y %H:%M')} UTC\n\n"
    )
    final += "\n\n".join(all_results)
    return final


async def check_single_club_all_members(club_tag: str) -> str:
    """
    Проверяет один клуб и возвращает HTML-список ВСЕХ участников
    с их временем последнего онлайна и цветовым статусом.
    """
    now = datetime.now(timezone.utc)
    semaphore = asyncio.Semaphore(API_SEMAPHORE_LIMIT)

    async with aiohttp.ClientSession() as session:
        club_data = await _get_club_info(session, club_tag)
        if not club_data:
            return f"❌ Клуб <code>#{club_tag}</code> — не удалось получить данные."

        club_name = _escape_html(club_data.get("name", f"#{club_tag}"))
        members = club_data.get("members", [])

        if not members:
            return (
                f"🏠 <b>{club_name}</b> (<code>#{club_tag}</code>)\n"
                f"Участников не найдено."
            )

        tasks = [
            _get_player_battlelog(session, member["tag"], semaphore)
            for member in members
        ]
        battlelogs = await asyncio.gather(*tasks)

        member_status_list = []

        for member, battlelog in zip(members, battlelogs):
            name = member.get("name", "???")
            tag = member.get("tag", "")
            role = member.get("role", "member")
            trophies = member.get("trophies", 0)

            last_time = _get_last_battle_time(battlelog) if battlelog else None

            if not last_time:
                seconds_inactive = float("inf")
                time_ago_str = "нет боёв"
                status_icon = "⚪"
            else:
                diff = now - last_time
                seconds_inactive = diff.total_seconds()

                if diff.days == 0:
                    hours = diff.seconds // 3600
                    if hours == 0:
                        minutes = (diff.seconds % 3600) // 60
                        time_ago_str = "только что" if minutes == 0 else f"{minutes} мин. назад"
                    else:
                        time_ago_str = f"{hours} ч. назад"
                elif diff.days == 1:
                    time_ago_str = "вчера"
                else:
                    time_ago_str = f"{diff.days} дн. назад"

                if seconds_inactive < 86400:      # < 24h
                    status_icon = "🟢"
                elif seconds_inactive < 259200:   # < 3 days
                    status_icon = "🟡"
                else:
                    status_icon = "🔴"

            member_status_list.append({
                "name": name,
                "tag": tag,
                "role": _translate_role(role),
                "trophies": trophies,
                "seconds_inactive": seconds_inactive,
                "time_ago_str": time_ago_str,
                "status_icon": status_icon,
            })

        # Самые неактивные сверху
        member_status_list.sort(key=lambda x: x["seconds_inactive"], reverse=True)

        header = (
            f"🏠 <b>{club_name}</b> (<code>#{club_tag}</code>)\n"
            f"👥 Всего участников: {len(members)}\n"
            f"Статусы: 🟢 &lt;24ч | 🟡 1–2 дня | 🔴 3+ дней | ⚪ нет боёв\n"
            f"{'─' * 28}\n"
        )

        lines = []
        for i, m in enumerate(member_status_list, 1):
            line = (
                f"{i}. {m['status_icon']} <b>{_escape_html(m['name'])}</b>\n"
                f"   🏆 {m['trophies']} | ⏰ {_escape_html(m['time_ago_str'])} | <code>{m['tag']}</code>\n"
            )
            lines.append(line)

        return header + "\n".join(lines)


def split_long_message(text: str, max_len: int = 4000) -> list[str]:
    """Публичный псевдоним для разбивки сообщений на чанки."""
    return _split_message(text, max_len)
