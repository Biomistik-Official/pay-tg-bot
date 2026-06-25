"""
Схема базы данных и инициализация SQLite.
"""

import os

import aiosqlite
from bot.config import config

# SQL для создания всех таблиц
CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id     INTEGER UNIQUE NOT NULL,
    username        TEXT,
    nickname        TEXT NOT NULL,
    player_tag      TEXT UNIQUE,
    club_name       TEXT,
    tickets_platinum INTEGER DEFAULT 0,
    tickets_gold     INTEGER DEFAULT 0,
    tickets_silver   INTEGER DEFAULT 0,
    tickets_bronze   INTEGER DEFAULT 0,
    tickets_support  INTEGER DEFAULT 0,
    tickets_help     INTEGER DEFAULT 0,
    points          REAL DEFAULT 0,
    is_blocked      INTEGER DEFAULT 0,
    registered_at   TEXT DEFAULT (datetime('now')),
    approved_requests INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS transactions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL,
    currency_type   TEXT NOT NULL CHECK(currency_type IN ('points', 'tickets_platinum', 'tickets_gold', 'tickets_silver', 'tickets_bronze', 'tickets_support', 'tickets_help')),
    operation       TEXT NOT NULL CHECK(operation IN ('add', 'subtract', 'set')),
    amount          REAL NOT NULL,
    reason          TEXT DEFAULT '',
    performed_by    INTEGER,
    created_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS requests (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL,
    currency_type   TEXT NOT NULL CHECK(currency_type IN ('points', 'tickets_platinum', 'tickets_gold', 'tickets_silver', 'tickets_bronze', 'tickets_support', 'tickets_help')),
    amount          REAL NOT NULL,
    reason          TEXT NOT NULL,
    status          TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'approved', 'rejected')),
    created_at      TEXT DEFAULT (datetime('now')),
    reviewed_at     TEXT,
    reviewed_by     INTEGER,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS shop_settings (
    key     TEXT PRIMARY KEY,
    value   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS shop_orders (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL,
    order_type      TEXT NOT NULL,
    details         TEXT NOT NULL,
    status          TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'completed', 'ignored')),
    created_at      TEXT DEFAULT (datetime('now')),
    completed_at    TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS staff (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL UNIQUE,
    granted_by  INTEGER,
    granted_at  TEXT DEFAULT (datetime('now')),
    is_active   INTEGER DEFAULT 1,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS quests (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    title           TEXT NOT NULL,
    description     TEXT NOT NULL,
    reward_type     TEXT NOT NULL,
    reward_amount   REAL NOT NULL,
    max_executors   INTEGER NOT NULL DEFAULT 1,
    deadline        TEXT,
    status          TEXT DEFAULT 'active' CHECK(status IN ('active', 'closed')),
    created_by      INTEGER,
    created_at      TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS quest_assignments (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    quest_id        INTEGER NOT NULL,
    user_id         INTEGER NOT NULL,
    status          TEXT DEFAULT 'taken' CHECK(status IN ('taken', 'submitted', 'approved', 'rejected')),
    taken_at        TEXT DEFAULT (datetime('now')),
    submitted_at    TEXT,
    submitted_text  TEXT,
    submitted_photo TEXT,
    reviewed_at     TEXT,
    reviewed_by     INTEGER,
    reject_reason   TEXT,
    FOREIGN KEY (quest_id) REFERENCES quests(id),
    FOREIGN KEY (user_id) REFERENCES users(id),
    UNIQUE(quest_id, user_id)
);
"""

# Дефолтные настройки магазина
DEFAULT_SHOP_SETTINGS = [
    ("withdraw_rate",        "9"),    # рублей за 1 балл
    ("withdraw_min",         "50"),   # минимум баллов для вывода
    ("item_bronze_active",   "1"),
    ("item_silver_active",   "1"),
    ("item_gold_active",     "1"),
    ("item_platinum_active", "1"),
    ("item_support_active",  "1"),
    ("item_help_active",     "1"),
    ("ticket_price_bronze",  "1.3"),  # баллов за 1 бронзовый тикет
    ("ticket_price_silver",  "2.5"),
    ("ticket_price_gold",    "5.0"),
    ("ticket_price_platinum","10.0"),
    ("ticket_price_support", "2.5"),
    # количество тикетов, списываемых за рулетку (по умолчанию 1)
    ("roulette_cost_bronze",  "1"),
    ("roulette_cost_silver",  "1"),
    ("roulette_cost_gold",    "1"),
    ("roulette_cost_platinum","1"),
    ("roulette_cost_support", "1"),
    ("roulette_cost_help",    "1"),
]


async def init_db() -> None:
    """Инициализировать базу данных и создать таблицы."""
    db_dir = os.path.dirname(config.database_path)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)

    async with aiosqlite.connect(config.database_path) as db:
        await db.executescript(CREATE_TABLES_SQL)
        await db.commit()

        # Миграция: Проверяем наличие колонок player_tag и club_name в users
        async with db.execute("PRAGMA table_info(users)") as cursor:
            columns = [row[1] for row in await cursor.fetchall()]

        if "player_tag" not in columns:
            await db.execute("ALTER TABLE users ADD COLUMN player_tag TEXT UNIQUE")
            await db.commit()

        if "club_name" not in columns:
            await db.execute("ALTER TABLE users ADD COLUMN club_name TEXT")
            await db.commit()

        if "tickets_help" not in columns:
            await db.execute("ALTER TABLE users ADD COLUMN tickets_help INTEGER DEFAULT 0")
            await db.commit()

        # Миграция: Обновляем CHECK constraint для transactions, если нужно
        async with db.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='transactions'") as cursor:
            row = await cursor.fetchone()
            if row and "tickets_help" not in row[0]:
                await db.execute("ALTER TABLE transactions RENAME TO transactions_old")
                await db.execute("""
                    CREATE TABLE transactions (
                        id              INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id         INTEGER NOT NULL,
                        currency_type   TEXT NOT NULL CHECK(currency_type IN ('points', 'tickets_platinum', 'tickets_gold', 'tickets_silver', 'tickets_bronze', 'tickets_support', 'tickets_help')),
                        operation       TEXT NOT NULL CHECK(operation IN ('add', 'subtract', 'set')),
                        amount          REAL NOT NULL,
                        reason          TEXT DEFAULT '',
                        performed_by    INTEGER,
                        created_at      TEXT DEFAULT (datetime('now')),
                        FOREIGN KEY (user_id) REFERENCES users(id)
                    )
                """)
                await db.execute("INSERT INTO transactions SELECT * FROM transactions_old")
                await db.execute("DROP TABLE transactions_old")
                await db.commit()

        # Миграция: Обновляем CHECK constraint для requests, если нужно
        async with db.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='requests'") as cursor:
            row = await cursor.fetchone()
            if row and "tickets_help" not in row[0]:
                await db.execute("ALTER TABLE requests RENAME TO requests_old")
                await db.execute("""
                    CREATE TABLE requests (
                        id              INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id         INTEGER NOT NULL,
                        currency_type   TEXT NOT NULL CHECK(currency_type IN ('points', 'tickets_platinum', 'tickets_gold', 'tickets_silver', 'tickets_bronze', 'tickets_support', 'tickets_help')),
                        amount          REAL NOT NULL,
                        reason          TEXT NOT NULL,
                        status          TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'approved', 'rejected')),
                        created_at      TEXT DEFAULT (datetime('now')),
                        reviewed_at     TEXT,
                        reviewed_by     INTEGER,
                        FOREIGN KEY (user_id) REFERENCES users(id)
                    )
                """)
                await db.execute("INSERT INTO requests SELECT * FROM requests_old")
                await db.execute("DROP TABLE requests_old")
                await db.commit()

        # Миграция: добавляем таблицы Staff, Quests, Quest Assignments если отсутствуют
        async with db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='staff'") as cur:
            if not await cur.fetchone():
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS staff (
                        id          INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id     INTEGER NOT NULL UNIQUE,
                        granted_by  INTEGER,
                        granted_at  TEXT DEFAULT (datetime('now')),
                        is_active   INTEGER DEFAULT 1,
                        FOREIGN KEY (user_id) REFERENCES users(id)
                    )
                """)
                await db.commit()

        async with db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='quests'") as cur:
            if not await cur.fetchone():
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS quests (
                        id              INTEGER PRIMARY KEY AUTOINCREMENT,
                        title           TEXT NOT NULL,
                        description     TEXT NOT NULL,
                        reward_type     TEXT NOT NULL,
                        reward_amount   REAL NOT NULL,
                        max_executors   INTEGER NOT NULL DEFAULT 1,
                        deadline        TEXT,
                        status          TEXT DEFAULT 'active' CHECK(status IN ('active', 'closed')),
                        created_by      INTEGER,
                        created_at      TEXT DEFAULT (datetime('now'))
                    )
                """)
                await db.commit()

        async with db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='quest_assignments'") as cur:
            if not await cur.fetchone():
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS quest_assignments (
                        id              INTEGER PRIMARY KEY AUTOINCREMENT,
                        quest_id        INTEGER NOT NULL,
                        user_id         INTEGER NOT NULL,
                        status          TEXT DEFAULT 'taken' CHECK(status IN ('taken', 'submitted', 'approved', 'rejected')),
                        taken_at        TEXT DEFAULT (datetime('now')),
                        submitted_at    TEXT,
                        submitted_text  TEXT,
                        submitted_photo TEXT,
                        reviewed_at     TEXT,
                        reviewed_by     INTEGER,
                        reject_reason   TEXT,
                        FOREIGN KEY (quest_id) REFERENCES quests(id),
                        FOREIGN KEY (user_id) REFERENCES users(id),
                        UNIQUE(quest_id, user_id)
                    )
                """)
                await db.commit()

        # Вставляем дефолтные настройки магазина (игнорируем, если уже есть)
        for key, value in DEFAULT_SHOP_SETTINGS:
            await db.execute(
                "INSERT OR IGNORE INTO shop_settings (key, value) VALUES (?, ?)",
                (key, value)
            )
        await db.commit()


def get_db():
    """Получить подключение к базе данных."""
    return aiosqlite.connect(config.database_path)
