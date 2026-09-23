"""
Все асинхронные SQL-запросы к базе данных.
"""

from typing import Optional, Any
from datetime import date
from math import isfinite
import aiosqlite
from bot.database.models import get_db
from bot.utils.treasury import DONATION_CURRENCIES, TREASURY_CURRENCIES


class TreasuryInsufficientFundsError(ValueError):
    pass


class TreasuryUserNotFoundError(ValueError):
    pass


#  USERS

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


#  TRANSACTIONS

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



#  REQUESTS

async def create_request(
    user_id: int,
    currency_type: str,
    amount: float,
    reason: str,
    media_type: str | None = None,
    media_file_id: str | None = None
) -> int:
    """Создать заявку на валюту. Возвращает ID заявки."""
    async with get_db() as db:
        cursor = await db.execute(
            """INSERT INTO requests (
                   user_id, currency_type, amount, reason, media_type, media_file_id
               ) VALUES (?, ?, ?, ?, ?, ?)""",
            (user_id, currency_type, amount, reason, media_type, media_file_id)
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


#  STATISTICS

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
                 COALESCE(SUM(tickets_support), 0),
                 COALESCE(SUM(tickets_help), 0)
               FROM users"""
        ) as c:
            row = await c.fetchone()
            tickets_platinum = row[0]
            tickets_gold = row[1]
            tickets_silver = row[2]
            tickets_bronze = row[3]
            tickets_support = row[4]
            tickets_help = row[5]
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
        "tickets_help": tickets_help,
        "total_points": total_points,
        "total_requests": total_requests,
        "approved": approved,
        "rejected": rejected,
        "last_30_days": last_30_days,
    }


#  SHOP SETTINGS

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


#  SHOP ORDERS

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


#  STAFF

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



async def get_staff_activity(user_id: int) -> dict:
    """Получить сохранённые показатели активности Staff."""
    async with get_db() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM staff_activities WHERE user_id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
    if row:
        return dict(row)
    return {
        "user_id": user_id,
        "activity_count": 0,
        "earned_points": 0,
        "earned_tickets": 0,
        "last_activity_at": None,
    }


async def get_treasuries() -> list[dict]:
    """Получить все казны с балансом баллов и числом участников."""
    async with get_db() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT t.*,
                   COALESCE(b.amount, 0) AS points_balance,
                   COUNT(DISTINCT tm.user_id) AS members_count,
                   MAX(CASE WHEN tt.operation_type IN
                       ('donation', 'manual_deposit', 'distribution_in')
                       THEN tt.created_at END) AS last_deposit
            FROM treasury t
            LEFT JOIN treasury_balances b
                ON b.treasury_id = t.id AND b.currency_type = 'points'
            LEFT JOIN treasury_members tm ON tm.treasury_id = t.id
            LEFT JOIN treasury_transactions tt ON tt.treasury_id = t.id
            GROUP BY t.id
            ORDER BY t.is_general DESC, t.id
        """) as cursor:
            return [dict(row) for row in await cursor.fetchall()]


async def get_treasury(treasury_id: int) -> Optional[dict]:
    """Получить казну и её текущие показатели."""
    async with get_db() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT t.*,
                   COALESCE(b.amount, 0) AS points_balance,
                   COUNT(DISTINCT tm.user_id) AS members_count,
                   MAX(CASE WHEN tt.operation_type IN
                       ('donation', 'manual_deposit', 'distribution_in')
                       THEN tt.created_at END) AS last_deposit
            FROM treasury t
            LEFT JOIN treasury_balances b
                ON b.treasury_id = t.id AND b.currency_type = 'points'
            LEFT JOIN treasury_members tm ON tm.treasury_id = t.id
            LEFT JOIN treasury_transactions tt ON tt.treasury_id = t.id
            WHERE t.id = ?
            GROUP BY t.id
        """, (treasury_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def get_treasury_by_code(code: str) -> Optional[dict]:
    """Получить казну по внутреннему коду."""
    async with get_db() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM treasury WHERE code = ?", (code,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def get_treasury_balances(treasury_id: int) -> dict[str, float]:
    """Получить все ненулевые балансы одной казны."""
    async with get_db() as db:
        async with db.execute(
            "SELECT currency_type, amount FROM treasury_balances WHERE treasury_id = ?",
            (treasury_id,),
        ) as cursor:
            return {row[0]: row[1] for row in await cursor.fetchall()}


async def get_treasury_history(
    treasury_id: int, limit: int = 8, offset: int = 0
) -> list[dict]:
    """Получить историю конкретной казны."""
    async with get_db() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT tt.*, u.nickname AS related_user_nickname,
                   actor.nickname AS actor_nickname,
                   target.name AS related_treasury_name,
                   target.emoji AS related_treasury_emoji
            FROM treasury_transactions tt
            LEFT JOIN users u ON u.id = tt.related_user_id
            LEFT JOIN users actor
                ON actor.telegram_id = tt.initiated_by_telegram_id
            LEFT JOIN treasury target ON target.id = tt.related_treasury_id
            WHERE tt.treasury_id = ?
            ORDER BY tt.created_at DESC, tt.id DESC
            LIMIT ? OFFSET ?
        """, (treasury_id, limit, offset)) as cursor:
            return [dict(row) for row in await cursor.fetchall()]


async def count_treasury_history(treasury_id: int) -> int:
    async with get_db() as db:
        async with db.execute(
            "SELECT COUNT(*) FROM treasury_transactions WHERE treasury_id = ?",
            (treasury_id,),
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0


def _validate_treasury_amount(currency_type: str, amount: float) -> None:
    if currency_type not in TREASURY_CURRENCIES:
        raise ValueError("Неизвестная валюта")
    if not isfinite(float(amount)) or amount <= 0:
        raise ValueError("Сумма должна быть положительной")
    if TREASURY_CURRENCIES[currency_type]["integer"] and not float(amount).is_integer():
        raise ValueError("Для этой валюты нужна целая сумма")


async def _balance_for_update(
    db: aiosqlite.Connection, treasury_id: int, currency_type: str
) -> float:
    await db.execute(
        """INSERT OR IGNORE INTO treasury_balances
           (treasury_id, currency_type, amount) VALUES (?, ?, 0)""",
        (treasury_id, currency_type),
    )
    async with db.execute(
        """SELECT amount FROM treasury_balances
           WHERE treasury_id = ? AND currency_type = ?""",
        (treasury_id, currency_type),
    ) as cursor:
        row = await cursor.fetchone()
        if row is None:
            raise ValueError("Казна не найдена")
        return float(row[0])


async def top_up_treasuries(
    amounts: dict[int, float],
    currency_type: str,
    initiated_by_telegram_id: int,
    related_user_id: int,
    reason: str,
    source: str,
    request_key: str,
) -> list[dict]:
    """Атомарно пополнить одну или несколько казен."""
    if not amounts or not request_key:
        raise ValueError("Не выбраны казны")
    for amount in amounts.values():
        _validate_treasury_amount(currency_type, amount)

    async with get_db() as db:
        db.row_factory = aiosqlite.Row
        await db.execute("BEGIN IMMEDIATE")
        try:
            placeholders = ",".join("?" for _ in amounts)
            async with db.execute(
                f"SELECT id FROM treasury WHERE id IN ({placeholders})",
                tuple(amounts),
            ) as cursor:
                found = {row[0] for row in await cursor.fetchall()}
            if found != set(amounts):
                raise ValueError("Одна из казен не найдена")

            results = []
            for treasury_id, amount in amounts.items():
                item_key = f"{request_key}:{treasury_id}"
                async with db.execute(
                    "SELECT id FROM treasury_transactions WHERE request_key = ?",
                    (item_key,),
                ) as cursor:
                    if await cursor.fetchone():
                        raise ValueError("Операция уже выполнена")
                before = await _balance_for_update(db, treasury_id, currency_type)
                after = before + float(amount)
                await db.execute(
                    """UPDATE treasury_balances
                       SET amount = ?, updated_at = datetime('now')
                       WHERE treasury_id = ? AND currency_type = ?""",
                    (after, treasury_id, currency_type),
                )
                cursor = await db.execute("""
                    INSERT INTO treasury_transactions (
                        treasury_id, operation_type, currency_type, amount,
                        balance_before, balance_after, related_user_id,
                        initiated_by_telegram_id, reason, source, request_key
                    ) VALUES (?, 'manual_deposit', ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    treasury_id, currency_type, amount, before, after,
                    related_user_id, initiated_by_telegram_id, reason,
                    source, item_key,
                ))
                results.append({
                    "id": cursor.lastrowid,
                    "treasury_id": treasury_id,
                    "balance_before": before,
                    "balance_after": after,
                })
            await db.commit()
            return results
        except Exception:
            await db.rollback()
            raise


async def donate_to_treasury(
    treasury_id: int,
    user_id: int,
    currency_type: str,
    amount: float,
    initiated_by_telegram_id: int,
    reason: str,
    request_key: str,
) -> dict:
    """Списать средства пользователя и атомарно зачислить их в казну."""
    if currency_type not in DONATION_CURRENCIES:
        raise ValueError("Эту валюту нельзя пожертвовать")
    _validate_treasury_amount(currency_type, amount)
    async with get_db() as db:
        db.row_factory = aiosqlite.Row
        await db.execute("BEGIN IMMEDIATE")
        try:
            async with db.execute(
                "SELECT id FROM treasury_transactions WHERE request_key = ?",
                (request_key,),
            ) as cursor:
                if await cursor.fetchone():
                    raise ValueError("Операция уже выполнена")
            async with db.execute(
                f"SELECT {currency_type} FROM users WHERE id = ?", (user_id,)
            ) as cursor:
                row = await cursor.fetchone()
            if not row:
                raise TreasuryUserNotFoundError("Пользователь не найден")
            if float(row[0]) < float(amount):
                raise TreasuryInsufficientFundsError("Недостаточно средств")

            await db.execute(
                f"UPDATE users SET {currency_type} = {currency_type} - ? WHERE id = ?",
                (amount, user_id),
            )
            await db.execute("""
                INSERT INTO transactions
                    (user_id, currency_type, operation, amount, reason, performed_by)
                VALUES (?, ?, 'subtract', ?, ?, ?)
            """, (
                user_id, currency_type, amount,
                f"Пожертвование в казну: {reason}".rstrip(": "),
                initiated_by_telegram_id,
            ))
            before = await _balance_for_update(db, treasury_id, currency_type)
            after = before + float(amount)
            await db.execute("""
                UPDATE treasury_balances
                SET amount = ?, updated_at = datetime('now')
                WHERE treasury_id = ? AND currency_type = ?
            """, (after, treasury_id, currency_type))
            cursor = await db.execute("""
                INSERT INTO treasury_transactions (
                    treasury_id, operation_type, currency_type, amount,
                    balance_before, balance_after, related_user_id,
                    initiated_by_telegram_id, reason, source, request_key
                ) VALUES (?, 'donation', ?, ?, ?, ?, ?, ?, ?, 'donation', ?)
            """, (
                treasury_id, currency_type, amount, before, after, user_id,
                initiated_by_telegram_id, reason, request_key,
            ))
            await db.commit()
            return {
                "id": cursor.lastrowid,
                "balance_before": before,
                "balance_after": after,
            }
        except Exception:
            await db.rollback()
            raise


async def spend_from_treasury(
    treasury_id: int,
    currency_type: str,
    amount: float,
    initiated_by_telegram_id: int,
    reason: str,
    request_key: str,
) -> dict:
    """Атомарно списать средства из выбранной казны."""
    _validate_treasury_amount(currency_type, amount)
    async with get_db() as db:
        await db.execute("BEGIN IMMEDIATE")
        try:
            before = await _balance_for_update(db, treasury_id, currency_type)
            if before < float(amount):
                raise TreasuryInsufficientFundsError("Недостаточно средств в казне")
            after = before - float(amount)
            await db.execute("""
                UPDATE treasury_balances
                SET amount = ?, updated_at = datetime('now')
                WHERE treasury_id = ? AND currency_type = ?
            """, (after, treasury_id, currency_type))
            cursor = await db.execute("""
                INSERT INTO treasury_transactions (
                    treasury_id, operation_type, currency_type, amount,
                    balance_before, balance_after, initiated_by_telegram_id,
                    reason, source, request_key
                ) VALUES (?, 'expense', ?, ?, ?, ?, ?, ?, 'owner', ?)
            """, (
                treasury_id, currency_type, amount, before, after,
                initiated_by_telegram_id, reason, request_key,
            ))
            await db.commit()
            return {
                "id": cursor.lastrowid,
                "balance_before": before,
                "balance_after": after,
            }
        except Exception:
            await db.rollback()
            raise


async def get_distribution_settings() -> list[dict]:
    async with get_db() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT t.id AS treasury_id, t.code, t.name, t.emoji,
                   COALESCE(s.percentage, 0) AS percentage
            FROM treasury t
            LEFT JOIN treasury_distribution_settings s ON s.treasury_id = t.id
            WHERE t.is_general = 0
            ORDER BY t.id
        """) as cursor:
            return [dict(row) for row in await cursor.fetchall()]


async def set_distribution_settings(
    percentages: dict[int, float], updated_by: int
) -> None:
    if not percentages or abs(sum(percentages.values()) - 100) > 0.000001:
        raise ValueError("Сумма процентов должна составлять ровно 100%")
    if any(value < 0 or value > 100 for value in percentages.values()):
        raise ValueError("Процент должен быть от 0 до 100")

    async with get_db() as db:
        await db.execute("BEGIN IMMEDIATE")
        try:
            placeholders = ",".join("?" for _ in percentages)
            async with db.execute(
                f"SELECT id FROM treasury WHERE is_general = 0 AND id IN ({placeholders})",
                tuple(percentages),
            ) as cursor:
                found = {row[0] for row in await cursor.fetchall()}
            if found != set(percentages):
                raise ValueError("Переданы не все отдельные казны")
            async with db.execute(
                "SELECT COUNT(*) FROM treasury WHERE is_general = 0"
            ) as cursor:
                total = (await cursor.fetchone())[0]
            if total != len(percentages):
                raise ValueError("Нужно указать проценты для всех казен")

            for treasury_id, percentage in percentages.items():
                await db.execute("""
                    INSERT INTO treasury_distribution_settings
                        (treasury_id, percentage, updated_at, updated_by)
                    VALUES (?, ?, datetime('now'), ?)
                    ON CONFLICT(treasury_id) DO UPDATE SET
                        percentage = excluded.percentage,
                        updated_at = excluded.updated_at,
                        updated_by = excluded.updated_by
                """, (treasury_id, percentage, updated_by))
            await db.commit()
        except Exception:
            await db.rollback()
            raise


async def distribute_general_treasury(
    amount: float,
    allocations: dict[int, float],
    initiated_by_telegram_id: int,
    reason: str,
    request_key: str,
) -> dict:
    """Атомарно распределить баллы общей казны по отдельным."""
    _validate_treasury_amount("points", amount)
    if not allocations or abs(sum(allocations.values()) - float(amount)) > 0.000001:
        raise ValueError("Сумма распределения не совпадает")
    if any(value < 0 for value in allocations.values()):
        raise ValueError("Доли не могут быть отрицательными")

    async with get_db() as db:
        await db.execute("BEGIN IMMEDIATE")
        try:
            async with db.execute(
                "SELECT id FROM treasury WHERE is_general = 1 LIMIT 1"
            ) as cursor:
                row = await cursor.fetchone()
            if not row:
                raise ValueError("Общая казна не найдена")
            general_id = row[0]
            before_general = await _balance_for_update(db, general_id, "points")
            if before_general < float(amount):
                raise TreasuryInsufficientFundsError("Недостаточно средств в общей казне")

            after_general = before_general - float(amount)
            await db.execute("""
                UPDATE treasury_balances
                SET amount = ?, updated_at = datetime('now')
                WHERE treasury_id = ? AND currency_type = 'points'
            """, (after_general, general_id))

            running_general = before_general
            for treasury_id, share in allocations.items():
                if share == 0:
                    continue
                async with db.execute(
                    "SELECT is_general FROM treasury WHERE id = ?", (treasury_id,)
                ) as cursor:
                    target = await cursor.fetchone()
                if not target or target[0]:
                    raise ValueError("Неверная отдельная казна")

                target_before = await _balance_for_update(db, treasury_id, "points")
                target_after = target_before + float(share)
                await db.execute("""
                    UPDATE treasury_balances
                    SET amount = ?, updated_at = datetime('now')
                    WHERE treasury_id = ? AND currency_type = 'points'
                """, (target_after, treasury_id))
                running_after = running_general - float(share)
                await db.execute("""
                    INSERT INTO treasury_transactions (
                        treasury_id, operation_type, currency_type, amount,
                        balance_before, balance_after, related_treasury_id,
                        initiated_by_telegram_id, reason, source, request_key
                    ) VALUES (?, 'distribution_out', 'points', ?, ?, ?, ?, ?, ?,
                              'distribution', ?)
                """, (
                    general_id, share, running_general, running_after, treasury_id,
                    initiated_by_telegram_id, reason,
                    f"{request_key}:out:{treasury_id}",
                ))
                await db.execute("""
                    INSERT INTO treasury_transactions (
                        treasury_id, operation_type, currency_type, amount,
                        balance_before, balance_after, related_treasury_id,
                        initiated_by_telegram_id, reason, source, request_key
                    ) VALUES (?, 'distribution_in', 'points', ?, ?, ?, ?, ?, ?,
                              'distribution', ?)
                """, (
                    treasury_id, share, target_before, target_after, general_id,
                    initiated_by_telegram_id, reason,
                    f"{request_key}:in:{treasury_id}",
                ))
                running_general = running_after
            await db.commit()
            return {
                "balance_before": before_general,
                "balance_after": after_general,
            }
        except Exception:
            await db.rollback()
            raise


async def get_treasury_members(treasury_id: int) -> list[dict]:
    async with get_db() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT tm.*, u.telegram_id, u.nickname, u.username, u.points,
                   a.activity_count, a.earned_points, a.earned_tickets,
                   a.last_activity_at
            FROM treasury_members tm
            JOIN users u ON u.id = tm.user_id
            JOIN staff s ON s.user_id = u.id AND s.is_active = 1
            LEFT JOIN staff_activities a ON a.user_id = u.id
            WHERE tm.treasury_id = ?
            ORDER BY LOWER(u.nickname)
        """, (treasury_id,)) as cursor:
            return [dict(row) for row in await cursor.fetchall()]


async def get_user_treasury(user_id: int) -> Optional[dict]:
    async with get_db() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT t.* FROM treasury_members tm
            JOIN treasury t ON t.id = tm.treasury_id
            WHERE tm.user_id = ?
        """, (user_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def assign_staff_to_treasury(
    treasury_id: int, user_id: int, assigned_by: int
) -> None:
    """Назначить Staff в казну, автоматически сняв старое назначение."""
    async with get_db() as db:
        await db.execute("BEGIN IMMEDIATE")
        try:
            async with db.execute(
                "SELECT 1 FROM staff WHERE user_id = ? AND is_active = 1", (user_id,)
            ) as cursor:
                if not await cursor.fetchone():
                    raise ValueError("Пользователь не является Staff")
            async with db.execute(
                "SELECT 1 FROM treasury WHERE id = ? AND is_general = 0", (treasury_id,)
            ) as cursor:
                if not await cursor.fetchone():
                    raise ValueError("Отдельная казна не найдена")
            await db.execute("DELETE FROM treasury_members WHERE user_id = ?", (user_id,))
            await db.execute("""
                INSERT INTO treasury_members
                    (treasury_id, user_id, assigned_by, assigned_at)
                VALUES (?, ?, ?, datetime('now'))
            """, (treasury_id, user_id, assigned_by))
            await db.commit()
        except Exception:
            await db.rollback()
            raise


async def remove_staff_from_treasury(treasury_id: int, user_id: int) -> None:
    async with get_db() as db:
        await db.execute(
            "DELETE FROM treasury_members WHERE treasury_id = ? AND user_id = ?",
            (treasury_id, user_id),
        )
        await db.commit()


async def payout_staff_from_treasury(
    treasury_id: int,
    payouts: dict[int, float],
    initiated_by_telegram_id: int,
    reason: str,
    request_key: str,
) -> dict:
    """Атомарно выдать баллы одному или нескольким участникам казны."""
    if not payouts or not request_key:
        raise ValueError("Не выбраны получатели")
    for amount in payouts.values():
        _validate_treasury_amount("points", amount)

    total = sum(float(amount) for amount in payouts.values())
    async with get_db() as db:
        await db.execute("BEGIN IMMEDIATE")
        try:
            before = await _balance_for_update(db, treasury_id, "points")
            if before < total:
                raise TreasuryInsufficientFundsError("Недостаточно средств в казне")

            placeholders = ",".join("?" for _ in payouts)
            async with db.execute(
                f"""SELECT user_id FROM treasury_members
                    WHERE treasury_id = ? AND user_id IN ({placeholders})""",
                (treasury_id, *payouts),
            ) as cursor:
                members = {row[0] for row in await cursor.fetchall()}
            if members != set(payouts):
                raise ValueError("Один из получателей не состоит в казне")

            running = before
            for user_id, amount in payouts.items():
                amount = float(amount)
                after = running - amount
                await db.execute(
                    "UPDATE users SET points = points + ? WHERE id = ?",
                    (amount, user_id),
                )
                await db.execute("""
                    INSERT INTO transactions
                        (user_id, currency_type, operation, amount, reason, performed_by)
                    VALUES (?, 'points', 'add', ?, ?, ?)
                """, (
                    user_id, amount, reason or "Выдача из казны",
                    initiated_by_telegram_id,
                ))
                await db.execute("""
                    INSERT INTO treasury_transactions (
                        treasury_id, operation_type, currency_type, amount,
                        balance_before, balance_after, related_user_id,
                        initiated_by_telegram_id, reason, source, request_key
                    ) VALUES (?, 'staff_payout', 'points', ?, ?, ?, ?, ?, ?,
                              'staff_payout', ?)
                """, (
                    treasury_id, amount, running, after, user_id,
                    initiated_by_telegram_id, reason,
                    f"{request_key}:{user_id}",
                ))
                running = after

            await db.execute("""
                UPDATE treasury_balances
                SET amount = ?, updated_at = datetime('now')
                WHERE treasury_id = ? AND currency_type = 'points'
            """, (running, treasury_id))
            await db.commit()
            return {
                "balance_before": before,
                "balance_after": running,
                "total": total,
            }
        except Exception:
            await db.rollback()
            raise
