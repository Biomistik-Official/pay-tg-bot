"""
Все асинхронные SQL-запросы к базе данных.
"""

from typing import Optional, Any
from datetime import datetime, date, timezone
import aiosqlite
from bot.database.models import get_db


# ══════════════════════════════════════════════
#  USERS
# ══════════════════════════════════════════════

async def create_user(
    telegram_id: int,
    username: Optional[str],
    nickname: str,
    player_tag: str,
    club_name: Optional[str]
) -> dict:
    """Создать нового пользователя."""
    async with get_db() as db:
        await db.execute(
            """INSERT INTO users (telegram_id, username, nickname, player_tag, club_name)
               VALUES (?, ?, ?, ?, ?)""",
            (telegram_id, username, nickname, player_tag, club_name)
        )
        await db.commit()
    return await get_user_by_telegram_id(telegram_id)


async def get_user_by_player_tag(player_tag: str) -> Optional[dict]:
    """Получить пользователя по тегу игрока Brawl Stars."""
    tag = player_tag.strip().upper()
    if not tag.startswith("#"):
        tag = "#" + tag
    async with get_db() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM users WHERE player_tag = ?", (tag,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def update_user_player_tag(telegram_id: int, player_tag: str, club_name: Optional[str]) -> None:
    """Обновить тег игрока и название клуба для пользователя."""
    tag = player_tag.strip().upper()
    if not tag.startswith("#"):
        tag = "#" + tag
    async with get_db() as db:
        await db.execute(
            "UPDATE users SET player_tag = ?, club_name = ? WHERE telegram_id = ?",
            (tag, club_name, telegram_id)
        )
        await db.commit()


async def update_user_club_name(telegram_id: int, club_name: Optional[str]) -> None:
    """Обновить название клуба пользователя."""
    async with get_db() as db:
        await db.execute(
            "UPDATE users SET club_name = ? WHERE telegram_id = ?",
            (club_name, telegram_id)
        )
        await db.commit()


async def get_user_by_telegram_id(telegram_id: int) -> Optional[dict]:
    """Получить пользователя по Telegram ID."""
    async with get_db() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def get_user_by_id(user_id: int) -> Optional[dict]:
    """Получить пользователя по внутреннему ID."""
    async with get_db() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM users WHERE id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def get_user_by_nickname(nickname: str) -> Optional[dict]:
    """Поиск пользователя по никнейму (без учёта регистра)."""
    async with get_db() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM users WHERE LOWER(nickname) LIKE LOWER(?)",
            (f"%{nickname}%",)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def get_all_users() -> list[dict]:
    """Получить всех пользователей."""
    async with get_db() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users ORDER BY registered_at DESC") as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def get_users_sorted(limit: int, offset: int) -> list[dict]:
    """Получить пользователей, отсортированных по никнейму A-Z."""
    async with get_db() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM users ORDER BY LOWER(nickname) ASC LIMIT ? OFFSET ?",
            (limit, offset)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def count_users() -> int:
    """Получить общее количество пользователей."""
    async with get_db() as db:
        async with db.execute("SELECT COUNT(*) FROM users") as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0


async def update_user_balance(
    user_id: int,
    currency_type: str,
    operation: str,
    amount: float
) -> None:
    """Обновить баланс пользователя."""
    if operation == "add":
        sql = f"UPDATE users SET {currency_type} = {currency_type} + ? WHERE id = ?"
    elif operation == "subtract":
        if currency_type == "points":
            sql = f"UPDATE users SET {currency_type} = {currency_type} - ? WHERE id = ?"
        else:
            sql = f"UPDATE users SET {currency_type} = MAX(0, {currency_type} - ?) WHERE id = ?"
    elif operation == "set":
        sql = f"UPDATE users SET {currency_type} = ? WHERE id = ?"
    else:
        raise ValueError(f"Неизвестная операция: {operation}")

    async with get_db() as db:
        await db.execute(sql, (amount, user_id))
        await db.commit()


async def increment_approved_requests(user_id: int) -> None:
    """Увеличить счётчик одобренных заявок."""
    async with get_db() as db:
        await db.execute(
            "UPDATE users SET approved_requests = approved_requests + 1 WHERE id = ?",
            (user_id,)
        )
        await db.commit()


async def set_user_blocked(telegram_id: int, block_status: Any) -> None:
    """Заблокировать / разблокировать пользователя."""
    async with get_db() as db:
        await db.execute(
            "UPDATE users SET is_blocked = ? WHERE telegram_id = ?",
            (int(block_status), telegram_id)
        )
        await db.commit()


async def update_user_nickname(telegram_id: int, new_nickname: str) -> None:
    """Изменить никнейм пользователя."""
    async with get_db() as db:
        await db.execute(
            "UPDATE users SET nickname = ? WHERE telegram_id = ?",
            (new_nickname, telegram_id)
        )
        await db.commit()


async def update_username(telegram_id: int, username: Optional[str]) -> None:
    """Обновить Telegram username пользователя."""
    async with get_db() as db:
        await db.execute(
            "UPDATE users SET username = ? WHERE telegram_id = ?",
            (username, telegram_id)
        )
        await db.commit()


# ══════════════════════════════════════════════
#  TRANSACTIONS
# ══════════════════════════════════════════════

async def add_transaction(
    user_id: int,
    currency_type: str,
    operation: str,
    amount: float,
    reason: str = "",
    performed_by: Optional[int] = None
) -> None:
    """Записать транзакцию в историю."""
    async with get_db() as db:
        await db.execute(
            """INSERT INTO transactions (user_id, currency_type, operation, amount, reason, performed_by)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (user_id, currency_type, operation, amount, reason, performed_by)
        )
        await db.commit()


async def get_user_transactions(user_id: int, limit: int = 10, offset: int = 0) -> list[dict]:
    """Получить историю операций пользователя."""
    async with get_db() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT t.*, u.nickname as performer_nickname
               FROM transactions t
               LEFT JOIN users u ON t.performed_by = u.telegram_id
               WHERE t.user_id = ?
               ORDER BY t.created_at DESC
               LIMIT ? OFFSET ?""",
            (user_id, limit, offset)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def count_user_transactions(user_id: int) -> int:
    """Подсчитать общее количество транзакций пользователя."""
    async with get_db() as db:
        async with db.execute(
            "SELECT COUNT(*) FROM transactions WHERE user_id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0


async def get_user_transactions_by_type(user_id: int, currency_type: str, limit: int = 10, offset: int = 0) -> list[dict]:
    """Получить историю операций пользователя по типу валюты."""
    async with get_db() as db:
        db.row_factory = aiosqlite.Row
        if currency_type == "tickets":
            sql = """SELECT t.*, u.nickname as performer_nickname
                   FROM transactions t
                   LEFT JOIN users u ON t.performed_by = u.telegram_id
                   WHERE t.user_id = ? AND t.currency_type LIKE 'tickets_%'
                   ORDER BY t.created_at DESC
                   LIMIT ? OFFSET ?"""
            params = (user_id, limit, offset)
        else:
            sql = """SELECT t.*, u.nickname as performer_nickname
                   FROM transactions t
                   LEFT JOIN users u ON t.performed_by = u.telegram_id
                   WHERE t.user_id = ? AND t.currency_type = ?
                   ORDER BY t.created_at DESC
                   LIMIT ? OFFSET ?"""
            params = (user_id, currency_type, limit, offset)

        async with db.execute(sql, params) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def count_user_transactions_by_type(user_id: int, currency_type: str) -> int:
    """Подсчитать количество транзакций пользователя по типу валюты."""
    async with get_db() as db:
        if currency_type == "tickets":
            sql = "SELECT COUNT(*) FROM transactions WHERE user_id = ? AND currency_type LIKE 'tickets_%'"
            params = (user_id,)
        else:
            sql = "SELECT COUNT(*) FROM transactions WHERE user_id = ? AND currency_type = ?"
            params = (user_id, currency_type)

        async with db.execute(sql, params) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0



# ══════════════════════════════════════════════
#  REQUESTS
# ══════════════════════════════════════════════

async def create_request(
    user_id: int,
    currency_type: str,
    amount: float,
    reason: str
) -> int:
    """Создать заявку на валюту. Возвращает ID заявки."""
    async with get_db() as db:
        cursor = await db.execute(
            """INSERT INTO requests (user_id, currency_type, amount, reason)
               VALUES (?, ?, ?, ?)""",
            (user_id, currency_type, amount, reason)
        )
        await db.commit()
        return cursor.lastrowid


async def get_request_by_id(request_id: int) -> Optional[dict]:
    """Получить заявку по ID."""
    async with get_db() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT r.*, u.nickname, u.username, u.telegram_id as user_telegram_id
               FROM requests r
               JOIN users u ON r.user_id = u.id
               WHERE r.id = ?""",
            (request_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def get_pending_requests() -> list[dict]:
    """Получить все активные заявки."""
    async with get_db() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT r.*, u.nickname, u.username, u.telegram_id as user_telegram_id
               FROM requests r
               JOIN users u ON r.user_id = u.id
               WHERE r.status = 'pending'
               ORDER BY r.created_at ASC"""
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def get_requests_history(limit: int = 20, offset: int = 0) -> list[dict]:
    """Получить историю заявок (одобренные и отклонённые)."""
    async with get_db() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT r.*, u.nickname, u.username, u.telegram_id as user_telegram_id
               FROM requests r
               JOIN users u ON r.user_id = u.id
               WHERE r.status != 'pending'
               ORDER BY r.reviewed_at DESC
               LIMIT ? OFFSET ?""",
            (limit, offset)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def update_request_status(
    request_id: int,
    status: str,
    reviewed_by: int
) -> None:
    """Обновить статус заявки."""
    async with get_db() as db:
        await db.execute(
            """UPDATE requests
               SET status = ?, reviewed_at = datetime('now'), reviewed_by = ?
               WHERE id = ?""",
            (status, reviewed_by, request_id)
        )
        await db.commit()


async def delete_request(request_id: int) -> None:
    """Удалить заявку из истории."""
    async with get_db() as db:
        await db.execute("DELETE FROM requests WHERE id = ?", (request_id,))
        await db.commit()


async def count_user_requests_today(user_id: int) -> int:
    """Подсчитать количество заявок пользователя за сегодня."""
    today = date.today().isoformat()
    async with get_db() as db:
        async with db.execute(
            """SELECT COUNT(*) FROM requests
               WHERE user_id = ? AND date(created_at) = ?""",
            (user_id, today)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0


async def count_requests_history() -> int:
    """Подсчитать количество обработанных заявок."""
    async with get_db() as db:
        async with db.execute(
            "SELECT COUNT(*) FROM requests WHERE status != 'pending'"
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0


# ══════════════════════════════════════════════
#  STATISTICS
# ══════════════════════════════════════════════

async def get_statistics() -> dict:
    """Получить общую статистику системы."""
    async with get_db() as db:
        async with db.execute("SELECT COUNT(*) FROM users") as c:
            total_users = (await c.fetchone())[0]

        async with db.execute(
            """SELECT 
                 COALESCE(SUM(tickets_platinum), 0),
                 COALESCE(SUM(tickets_gold), 0),
                 COALESCE(SUM(tickets_silver), 0),
                 COALESCE(SUM(tickets_bronze), 0),
                 COALESCE(SUM(tickets_support), 0)
               FROM users"""
        ) as c:
            row = await c.fetchone()
            tickets_platinum = row[0]
            tickets_gold = row[1]
            tickets_silver = row[2]
            tickets_bronze = row[3]
            tickets_support = row[4]
            total_tickets = sum(row)

        async with db.execute("SELECT COALESCE(SUM(points), 0) FROM users") as c:
            total_points = (await c.fetchone())[0]

        async with db.execute("SELECT COUNT(*) FROM requests") as c:
            total_requests = (await c.fetchone())[0]

        async with db.execute(
            "SELECT COUNT(*) FROM requests WHERE status = 'approved'"
        ) as c:
            approved = (await c.fetchone())[0]

        async with db.execute(
            "SELECT COUNT(*) FROM requests WHERE status = 'rejected'"
        ) as c:
            rejected = (await c.fetchone())[0]

        async with db.execute(
            """SELECT COUNT(*) FROM requests
               WHERE created_at >= datetime('now', '-30 days')"""
        ) as c:
            last_30_days = (await c.fetchone())[0]

    return {
        "total_users": total_users,
        "total_tickets": total_tickets,
        "tickets_platinum": tickets_platinum,
        "tickets_gold": tickets_gold,
        "tickets_silver": tickets_silver,
        "tickets_bronze": tickets_bronze,
        "tickets_support": tickets_support,
        "total_points": total_points,
        "total_requests": total_requests,
        "approved": approved,
        "rejected": rejected,
        "last_30_days": last_30_days,
    }


# ══════════════════════════════════════════════
#  SHOP SETTINGS
# ══════════════════════════════════════════════

async def get_shop_settings() -> dict:
    """Получить все настройки магазина."""
    async with get_db() as db:
        async with db.execute("SELECT key, value FROM shop_settings") as cursor:
            rows = await cursor.fetchall()
            return {row[0]: row[1] for row in rows}


async def get_shop_setting(key: str, default: str = "0") -> str:
    """Получить одну настройку магазина."""
    async with get_db() as db:
        async with db.execute(
            "SELECT value FROM shop_settings WHERE key = ?", (key,)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else default


async def update_shop_setting(key: str, value: str) -> None:
    """Обновить настройку магазина."""
    async with get_db() as db:
        await db.execute(
            "INSERT OR REPLACE INTO shop_settings (key, value) VALUES (?, ?)",
            (key, value)
        )
        await db.commit()


# ══════════════════════════════════════════════
#  SHOP ORDERS
# ══════════════════════════════════════════════

async def create_shop_order(user_id: int, order_type: str, details: str) -> int:
    """Создать заявку магазина. Возвращает ID заявки."""
    async with get_db() as db:
        cursor = await db.execute(
            """INSERT INTO shop_orders (user_id, order_type, details)
               VALUES (?, ?, ?)""",
            (user_id, order_type, details)
        )
        await db.commit()
        return cursor.lastrowid


async def get_pending_shop_orders() -> list[dict]:
    """Получить все активные заявки магазина (To-Do)."""
    async with get_db() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT o.*, u.nickname, u.username, u.telegram_id as user_telegram_id
               FROM shop_orders o
               JOIN users u ON o.user_id = u.id
               WHERE o.status = 'pending'
               ORDER BY o.created_at ASC"""
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def get_shop_order_by_id(order_id: int) -> Optional[dict]:
    """Получить заявку магазина по ID."""
    async with get_db() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT o.*, u.nickname, u.username, u.telegram_id as user_telegram_id
               FROM shop_orders o
               JOIN users u ON o.user_id = u.id
               WHERE o.id = ?""",
            (order_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def update_shop_order_status(order_id: int, status: str) -> None:
    """Обновить статус заявки магазина (completed / ignored)."""
    async with get_db() as db:
        await db.execute(
            """UPDATE shop_orders
               SET status = ?, completed_at = datetime('now')
               WHERE id = ?""",
            (status, order_id)
        )
        await db.commit()


async def get_shop_orders_history(limit: int = 20, offset: int = 0) -> list[dict]:
    """Получить историю заявок магазина (завершённые и игнорированные)."""
    async with get_db() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT o.*, u.nickname, u.username, u.telegram_id as user_telegram_id
               FROM shop_orders o
               JOIN users u ON o.user_id = u.id
               WHERE o.status != 'pending'
               ORDER BY o.completed_at DESC
               LIMIT ? OFFSET ?""",
            (limit, offset)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def count_shop_orders_history() -> int:
    """Подсчитать количество обработанных заявок магазина."""
    async with get_db() as db:
        async with db.execute(
            "SELECT COUNT(*) FROM shop_orders WHERE status != 'pending'"
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0


async def count_pending_shop_orders() -> int:
    """Подсчитать количество активных заявок магазина."""
    async with get_db() as db:
        async with db.execute(
            "SELECT COUNT(*) FROM shop_orders WHERE status = 'pending'"
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0


# ══════════════════════════════════════════════
#  STAFF
# ══════════════════════════════════════════════

async def add_staff(user_id: int, granted_by: int) -> None:
    """Выдать пользователю роль Staff (или реактивировать)."""
    async with get_db() as db:
        await db.execute(
            """INSERT INTO staff (user_id, granted_by, granted_at, is_active)
               VALUES (?, ?, datetime('now'), 1)
               ON CONFLICT(user_id) DO UPDATE SET
                   granted_by = excluded.granted_by,
                   granted_at = excluded.granted_at,
                   is_active  = 1""",
            (user_id, granted_by)
        )
        await db.commit()


async def remove_staff(user_id: int) -> None:
    """Снять роль Staff с пользователя (деактивация)."""
    async with get_db() as db:
        await db.execute(
            "UPDATE staff SET is_active = 0 WHERE user_id = ?",
            (user_id,)
        )
        await db.commit()


async def get_staff_by_user_id(user_id: int) -> Optional[dict]:
    """Получить запись Staff по внутреннему ID пользователя."""
    async with get_db() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM staff WHERE user_id = ? AND is_active = 1", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def is_staff(telegram_id: int) -> bool:
    """Проверить, является ли пользователь активным Staff."""
    async with get_db() as db:
        async with db.execute(
            """SELECT s.id FROM staff s
               JOIN users u ON s.user_id = u.id
               WHERE u.telegram_id = ? AND s.is_active = 1""",
            (telegram_id,)
        ) as cursor:
            return await cursor.fetchone() is not None


async def get_all_staff() -> list[dict]:
    """Получить всех активных Staff с данными пользователей."""
    async with get_db() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT s.*, u.nickname, u.username, u.telegram_id,
                      u.points, u.tickets_platinum, u.tickets_gold,
                      u.tickets_silver, u.tickets_bronze, u.tickets_support, u.tickets_help
               FROM staff s
               JOIN users u ON s.user_id = u.id
               WHERE s.is_active = 1
               ORDER BY s.granted_at DESC"""
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def get_staff_stats(user_id: int) -> dict:
    """Получить статистику Staff: выполнено квестов, баллы, тикеты, последняя активность."""
    async with get_db() as db:
        async with db.execute(
            """SELECT COUNT(*) FROM quest_assignments
               WHERE user_id = ? AND status = 'approved'""",
            (user_id,)
        ) as cursor:
            completed = (await cursor.fetchone())[0]

        async with db.execute(
            """SELECT COALESCE(SUM(q.reward_amount), 0)
               FROM quest_assignments qa
               JOIN quests q ON qa.quest_id = q.id
               WHERE qa.user_id = ? AND qa.status = 'approved' AND q.reward_type = 'points'""",
            (user_id,)
        ) as cursor:
            earned_points = (await cursor.fetchone())[0]

        async with db.execute(
            """SELECT COALESCE(SUM(q.reward_amount), 0)
               FROM quest_assignments qa
               JOIN quests q ON qa.quest_id = q.id
               WHERE qa.user_id = ? AND qa.status = 'approved' AND q.reward_type LIKE 'tickets_%'""",
            (user_id,)
        ) as cursor:
            earned_tickets = (await cursor.fetchone())[0]

        async with db.execute(
            """SELECT MAX(qa.reviewed_at)
               FROM quest_assignments qa
               WHERE qa.user_id = ? AND qa.status = 'approved'""",
            (user_id,)
        ) as cursor:
            last_activity = (await cursor.fetchone())[0]

    return {
        "completed": completed,
        "earned_points": earned_points,
        "earned_tickets": earned_tickets,
        "last_activity": last_activity,
    }


async def get_staff_leaderboard() -> list[dict]:
    """Получить рейтинг Staff по количеству выполненных квестов."""
    async with get_db() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT u.nickname, u.telegram_id,
                      COUNT(qa.id) as completed_quests,
                      COALESCE(SUM(CASE WHEN q.reward_type='points' THEN q.reward_amount ELSE 0 END), 0) as earned_points
               FROM staff s
               JOIN users u ON s.user_id = u.id
               LEFT JOIN quest_assignments qa ON qa.user_id = s.user_id AND qa.status = 'approved'
               LEFT JOIN quests q ON qa.quest_id = q.id
               WHERE s.is_active = 1
               GROUP BY s.user_id
               ORDER BY completed_quests DESC, earned_points DESC"""
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


# ══════════════════════════════════════════════
#  QUESTS
# ══════════════════════════════════════════════

async def create_quest(
    title: str,
    description: str,
    reward_type: str,
    reward_amount: float,
    max_executors: int,
    deadline: Optional[str],
    created_by: int
) -> int:
    """Создать квест. Возвращает ID квеста."""
    async with get_db() as db:
        cursor = await db.execute(
            """INSERT INTO quests (title, description, reward_type, reward_amount,
                                   max_executors, deadline, created_by)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (title, description, reward_type, reward_amount, max_executors, deadline, created_by)
        )
        await db.commit()
        return cursor.lastrowid


async def get_quest_by_id(quest_id: int) -> Optional[dict]:
    """Получить квест по ID."""
    async with get_db() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM quests WHERE id = ?", (quest_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def get_all_active_quests() -> list[dict]:
    """Получить все активные квесты."""
    async with get_db() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM quests WHERE status = 'active' ORDER BY created_at DESC"
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def get_all_quests() -> list[dict]:
    """Получить все квесты (для Owner)."""
    async with get_db() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM quests ORDER BY created_at DESC"
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def update_quest(quest_id: int, **fields) -> None:
    """Обновить поля квеста."""
    allowed = {"title", "description", "reward_type", "reward_amount",
                "max_executors", "deadline", "status"}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [quest_id]
    async with get_db() as db:
        await db.execute(f"UPDATE quests SET {set_clause} WHERE id = ?", values)
        await db.commit()


async def close_quest(quest_id: int) -> None:
    """Закрыть квест."""
    await update_quest(quest_id, status="closed")


async def delete_quest(quest_id: int) -> None:
    """Удалить квест и все его назначения."""
    async with get_db() as db:
        await db.execute("DELETE FROM quest_assignments WHERE quest_id = ?", (quest_id,))
        await db.execute("DELETE FROM quests WHERE id = ?", (quest_id,))
        await db.commit()


async def get_quest_stats(quest_id: int) -> dict:
    """Статистика квеста: взято, отправлено, одобрено, отклонено."""
    async with get_db() as db:
        async with db.execute(
            "SELECT COUNT(*) FROM quest_assignments WHERE quest_id = ?", (quest_id,)
        ) as c:
            total = (await c.fetchone())[0]
        async with db.execute(
            "SELECT COUNT(*) FROM quest_assignments WHERE quest_id = ? AND status = 'taken'", (quest_id,)
        ) as c:
            taken = (await c.fetchone())[0]
        async with db.execute(
            "SELECT COUNT(*) FROM quest_assignments WHERE quest_id = ? AND status = 'submitted'", (quest_id,)
        ) as c:
            submitted = (await c.fetchone())[0]
        async with db.execute(
            "SELECT COUNT(*) FROM quest_assignments WHERE quest_id = ? AND status = 'approved'", (quest_id,)
        ) as c:
            approved = (await c.fetchone())[0]
        async with db.execute(
            "SELECT COUNT(*) FROM quest_assignments WHERE quest_id = ? AND status = 'rejected'", (quest_id,)
        ) as c:
            rejected = (await c.fetchone())[0]
    return {
        "total": total, "taken": taken,
        "submitted": submitted, "approved": approved, "rejected": rejected,
    }


# ══════════════════════════════════════════════
#  QUEST ASSIGNMENTS
# ══════════════════════════════════════════════

async def take_quest(quest_id: int, user_id: int) -> bool:
    """Взять квест. Возвращает True при успехе, False если уже взят или лимит."""
    async with get_db() as db:
        # Проверить лимит
        async with db.execute(
            "SELECT max_executors FROM quests WHERE id = ?", (quest_id,)
        ) as c:
            row = await c.fetchone()
            if not row:
                return False
            max_exec = row[0]

        async with db.execute(
            "SELECT COUNT(*) FROM quest_assignments WHERE quest_id = ?", (quest_id,)
        ) as c:
            current = (await c.fetchone())[0]

        if current >= max_exec:
            return False

        try:
            await db.execute(
                """INSERT INTO quest_assignments (quest_id, user_id)
                   VALUES (?, ?)""",
                (quest_id, user_id)
            )
            await db.commit()
            return True
        except Exception:
            return False


async def get_user_quest_assignment(quest_id: int, user_id: int) -> Optional[dict]:
    """Получить назначение конкретного пользователя на квест."""
    async with get_db() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM quest_assignments WHERE quest_id = ? AND user_id = ?",
            (quest_id, user_id)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def get_assignment_by_id(assignment_id: int) -> Optional[dict]:
    """Получить назначение по ID с данными квеста и пользователя."""
    async with get_db() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT qa.*, q.title, q.reward_type, q.reward_amount,
                      u.nickname, u.username, u.telegram_id as user_telegram_id,
                      u.id as user_db_id
               FROM quest_assignments qa
               JOIN quests q ON qa.quest_id = q.id
               JOIN users u ON qa.user_id = u.id
               WHERE qa.id = ?""",
            (assignment_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def count_quest_executors(quest_id: int) -> int:
    """Подсчитать текущее количество исполнителей квеста."""
    async with get_db() as db:
        async with db.execute(
            "SELECT COUNT(*) FROM quest_assignments WHERE quest_id = ?", (quest_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0


async def submit_quest(assignment_id: int, text: Optional[str], photo: Optional[str]) -> None:
    """Отправить квест на проверку."""
    async with get_db() as db:
        await db.execute(
            """UPDATE quest_assignments
               SET status = 'submitted', submitted_at = datetime('now'),
                   submitted_text = ?, submitted_photo = ?
               WHERE id = ?""",
            (text, photo, assignment_id)
        )
        await db.commit()


async def approve_assignment(assignment_id: int, reviewed_by: int) -> None:
    """Одобрить выполнение квеста."""
    async with get_db() as db:
        await db.execute(
            """UPDATE quest_assignments
               SET status = 'approved', reviewed_at = datetime('now'), reviewed_by = ?
               WHERE id = ?""",
            (reviewed_by, assignment_id)
        )
        await db.commit()


async def reject_assignment(assignment_id: int, reviewed_by: int, reason: Optional[str]) -> None:
    """Отклонить выполнение квеста."""
    async with get_db() as db:
        await db.execute(
            """UPDATE quest_assignments
               SET status = 'rejected', reviewed_at = datetime('now'),
                   reviewed_by = ?, reject_reason = ?
               WHERE id = ?""",
            (reviewed_by, reason, assignment_id)
        )
        await db.commit()


async def get_submitted_assignments() -> list[dict]:
    """Получить все назначения, отправленные на проверку (для Owner)."""
    async with get_db() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT qa.*, q.title, q.reward_type, q.reward_amount,
                      u.nickname, u.username, u.telegram_id as user_telegram_id,
                      u.id as user_db_id
               FROM quest_assignments qa
               JOIN quests q ON qa.quest_id = q.id
               JOIN users u ON qa.user_id = u.id
               WHERE qa.status = 'submitted'
               ORDER BY qa.submitted_at ASC"""
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def get_user_active_assignments(user_id: int) -> list[dict]:
    """Получить активные квесты пользователя (taken + submitted)."""
    async with get_db() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT qa.*, q.title, q.description, q.reward_type, q.reward_amount,
                      q.deadline, q.status as quest_status
               FROM quest_assignments qa
               JOIN quests q ON qa.quest_id = q.id
               WHERE qa.user_id = ? AND qa.status IN ('taken', 'submitted')
               ORDER BY qa.taken_at DESC""",
            (user_id,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def get_user_quest_history(user_id: int) -> list[dict]:
    """Получить историю квестов пользователя (approved + rejected)."""
    async with get_db() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT qa.*, q.title, q.reward_type, q.reward_amount, q.deadline
               FROM quest_assignments qa
               JOIN quests q ON qa.quest_id = q.id
               WHERE qa.user_id = ? AND qa.status IN ('approved', 'rejected')
               ORDER BY qa.reviewed_at DESC""",
            (user_id,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def get_all_users_telegram_ids() -> list[int]:
    """Получить telegram_id всех незаблокированных пользователей (для рассылок)."""
    async with get_db() as db:
        async with db.execute(
            "SELECT telegram_id FROM users WHERE is_blocked = 0"
        ) as cursor:
            rows = await cursor.fetchall()
            return [r[0] for r in rows]


async def get_staff_telegram_ids() -> list[int]:
    """Получить telegram_id всех активных Staff."""
    async with get_db() as db:
        async with db.execute(
            """SELECT u.telegram_id FROM staff s
               JOIN users u ON s.user_id = u.id
               WHERE s.is_active = 1 AND u.is_blocked = 0"""
        ) as cursor:
            rows = await cursor.fetchall()
            return [r[0] for r in rows]


async def delete_assignment(assignment_id: int) -> None:
    """Удалить назначение квеста."""
    async with get_db() as db:
        await db.execute("DELETE FROM quest_assignments WHERE id = ?", (assignment_id,))
        await db.commit()

