"""
Схема базы данных и инициализация SQLite.
"""

import os

import aiosqlite
from bot.config import config
from bot.utils.ranks import RANK_META

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
    rubles          REAL DEFAULT 0,
    stars           INTEGER DEFAULT 0,
    unwarns         INTEGER DEFAULT 0,
    unmutes         INTEGER DEFAULT 0,
    is_blocked      INTEGER DEFAULT 0,
    registered_at   TEXT DEFAULT (datetime('now')),
    approved_requests INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS transactions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL,
    currency_type   TEXT NOT NULL CHECK(currency_type IN ('points', 'tickets_platinum', 'tickets_gold', 'tickets_silver', 'tickets_bronze', 'tickets_support', 'tickets_help', 'unwarns', 'unmutes', 'rubles', 'stars')),
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
    rank        TEXT DEFAULT 'novice',
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS quests (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    title           TEXT NOT NULL,
    description     TEXT NOT NULL,
    reward_type     TEXT NOT NULL,
    reward_amount   REAL NOT NULL,
    reward_mode     TEXT NOT NULL DEFAULT 'flat' CHECK(reward_mode IN ('flat', 'coefficient')),
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
    applied_coefficient REAL,
    paid_amount     REAL,
    FOREIGN KEY (quest_id) REFERENCES quests(id),
    FOREIGN KEY (user_id) REFERENCES users(id),
    UNIQUE(quest_id, user_id)
);

CREATE TABLE IF NOT EXISTS staff_rank_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,
    old_rank    TEXT,
    new_rank    TEXT NOT NULL,
    changed_by  INTEGER,
    changed_at  TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS staff_rank_coefficients (
    rank        TEXT PRIMARY KEY,
    coefficient REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS staff_categories (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE,
    description TEXT DEFAULT '',
    coefficient REAL NOT NULL DEFAULT 1,
    comment     TEXT DEFAULT '',
    created_at  TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS staff_category_operations (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    category_id     INTEGER,
    operation_type  TEXT NOT NULL CHECK(operation_type IN ('salary', 'penalty')),
    scope           TEXT NOT NULL CHECK(scope IN ('category', 'single')),
    base_amount     REAL NOT NULL,
    total_amount    REAL NOT NULL DEFAULT 0,
    recipients_count INTEGER NOT NULL DEFAULT 0,
    performed_by    INTEGER,
    created_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (category_id) REFERENCES staff_categories(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS staff_category_operation_items (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    operation_id    INTEGER NOT NULL,
    user_id         INTEGER NOT NULL,
    amount          REAL NOT NULL,
    rank_at_time    TEXT,
    rank_coef       REAL,
    category_coef   REAL,
    FOREIGN KEY (operation_id) REFERENCES staff_category_operations(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
"""

# Дефолтные категории Staff
DEFAULT_STAFF_CATEGORIES = [
    (
        "🎯 Активности",
        "Администрация отвечающая за активность и отыгровку всех ивентов клана "
        "на максимально возможную. Если администрация пропустит хоть 1 человека "
        "по неактиву выше недопустимого на день, то получит штраф. "
        "Недельная ЗП = коэффициент × 10 / количество людей в категории.",
        10.0,
    ),
    (
        "🏆 Достижения",
        "Администрация отвечающая за обновление списков достижений. Должны быть "
        "указаны правильно все достижения во всех кланах, исключение в 1 погрешность. "
        "Недельная ЗП = коэффициент × 20 / количество людей в категории.",
        20.0,
    ),
    (
        "🛡 Проверочная",
        "Администрация, решающая все вопросы клана. Недельной ЗП нет, всё зависит "
        "от вашего вклада. Примерная ЗП 0–50 баллов.",
        1.0,
    ),
]

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

        if "unwarns" not in columns:
            await db.execute("ALTER TABLE users ADD COLUMN unwarns INTEGER DEFAULT 0")
            await db.commit()

        if "unmutes" not in columns:
            await db.execute("ALTER TABLE users ADD COLUMN unmutes INTEGER DEFAULT 0")
            await db.commit()

        if "rubles" not in columns:
            await db.execute("ALTER TABLE users ADD COLUMN rubles REAL DEFAULT 0")
            await db.commit()

        if "stars" not in columns:
            await db.execute("ALTER TABLE users ADD COLUMN stars INTEGER DEFAULT 0")
            await db.commit()

        # Миграция: Обновляем CHECK constraint для transactions, если нужно
        async with db.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='transactions'") as cursor:
            row = await cursor.fetchone()
            if row and ("unwarns" not in row[0] or "unmutes" not in row[0] or "rubles" not in row[0] or "stars" not in row[0]):
                await db.execute("ALTER TABLE transactions RENAME TO transactions_old")
                await db.execute("""
                    CREATE TABLE transactions (
                        id              INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id         INTEGER NOT NULL,
                        currency_type   TEXT NOT NULL CHECK(currency_type IN ('points', 'tickets_platinum', 'tickets_gold', 'tickets_silver', 'tickets_bronze', 'tickets_support', 'tickets_help', 'unwarns', 'unmutes', 'rubles', 'stars')),
                        operation       TEXT NOT NULL CHECK(operation IN ('add', 'subtract', 'set')),
                        amount          REAL NOT NULL,
                        reason          TEXT DEFAULT '',
                        performed_by    INTEGER,
                        created_at      TEXT DEFAULT (datetime('now')),
                        FOREIGN KEY (user_id) REFERENCES users(id)
                    )
                """)
                await db.execute("INSERT INTO transactions (id, user_id, currency_type, operation, amount, reason, performed_by, created_at) SELECT id, user_id, currency_type, operation, amount, reason, performed_by, created_at FROM transactions_old")
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

        # Миграция: ранги Staff — колонка rank в таблице staff
        async with db.execute("PRAGMA table_info(staff)") as cursor:
            staff_columns = [row[1] for row in await cursor.fetchall()]
        if "rank" not in staff_columns:
            await db.execute("ALTER TABLE staff ADD COLUMN rank TEXT DEFAULT 'novice'")
            await db.commit()

        # Миграция: колонка category_id в staff
        if "category_id" not in staff_columns:
            await db.execute("ALTER TABLE staff ADD COLUMN category_id INTEGER")
            await db.commit()

        # Миграция: способ начисления награды — колонка reward_mode в таблице quests
        async with db.execute("PRAGMA table_info(quests)") as cursor:
            quest_columns = [row[1] for row in await cursor.fetchall()]
        if "reward_mode" not in quest_columns:
            await db.execute("ALTER TABLE quests ADD COLUMN reward_mode TEXT NOT NULL DEFAULT 'flat'")
            await db.commit()

        # Миграция: применённый коэффициент и фактическая награда в quest_assignments
        async with db.execute("PRAGMA table_info(quest_assignments)") as cursor:
            qa_columns = [row[1] for row in await cursor.fetchall()]
        if "applied_coefficient" not in qa_columns:
            await db.execute("ALTER TABLE quest_assignments ADD COLUMN applied_coefficient REAL")
            await db.commit()
        if "paid_amount" not in qa_columns:
            await db.execute("ALTER TABLE quest_assignments ADD COLUMN paid_amount REAL")
            await db.commit()

        # Вставляем дефолтные настройки магазина (игнорируем, если уже есть)
        for key, value in DEFAULT_SHOP_SETTINGS:
            await db.execute(
                "INSERT OR IGNORE INTO shop_settings (key, value) VALUES (?, ?)",
                (key, value)
            )
        await db.commit()

        # Вставляем дефолтные коэффициенты рангов Staff (игнорируем, если уже есть)
        for rank, meta in RANK_META.items():
            await db.execute(
                "INSERT OR IGNORE INTO staff_rank_coefficients (rank, coefficient) VALUES (?, ?)",
                (rank, meta["default_coef"])
            )
        await db.commit()

        # Дефолтные категории Staff (если таблица пуста)
        async with db.execute("SELECT COUNT(*) FROM staff_categories") as cur:
            cnt = (await cur.fetchone())[0]
        if cnt == 0:
            for name, desc, coef in DEFAULT_STAFF_CATEGORIES:
                await db.execute(
                    "INSERT INTO staff_categories (name, description, coefficient) VALUES (?, ?, ?)",
                    (name, desc, coef)
                )
            await db.commit()

        # Одноразовая миграция: обновить описания дефолтных категорий и коэффициенты
        # рангов до новых значений. Флаг хранится в shop_settings.
        async with db.execute(
            "SELECT value FROM shop_settings WHERE key = 'migration_v2_categories_ranks'"
        ) as cur:
            row = await cur.fetchone()
        if not row:
            for name, desc, coef in DEFAULT_STAFF_CATEGORIES:
                await db.execute(
                    """UPDATE staff_categories
                       SET description = ?, coefficient = ?
                       WHERE name = ?""",
                    (desc, coef, name),
                )
            for rank, meta in RANK_META.items():
                await db.execute(
                    """UPDATE staff_rank_coefficients
                       SET coefficient = ?
                       WHERE rank = ?""",
                    (meta["default_coef"], rank),
                )
            await db.execute(
                "INSERT OR REPLACE INTO shop_settings (key, value) VALUES (?, ?)",
                ("migration_v2_categories_ranks", "1"),
            )
            await db.commit()


def get_db():
    """Получить подключение к базе данных."""
    return aiosqlite.connect(config.database_path)
