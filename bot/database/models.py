"""Схема базы данных и инициализация SQLite."""

import os

import aiosqlite

from bot.config import config


CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id         INTEGER UNIQUE NOT NULL,
    username            TEXT,
    nickname            TEXT NOT NULL,
    player_tag          TEXT UNIQUE,
    club_name           TEXT,
    tickets_platinum    INTEGER DEFAULT 0,
    tickets_gold        INTEGER DEFAULT 0,
    tickets_silver      INTEGER DEFAULT 0,
    tickets_bronze      INTEGER DEFAULT 0,
    tickets_support     INTEGER DEFAULT 0,
    tickets_help        INTEGER DEFAULT 0,
    points              REAL DEFAULT 0,
    rubles              REAL DEFAULT 0,
    stars               INTEGER DEFAULT 0,
    unwarns             INTEGER DEFAULT 0,
    unmutes             INTEGER DEFAULT 0,
    is_blocked          INTEGER DEFAULT 0,
    registered_at       TEXT DEFAULT (datetime('now')),
    approved_requests   INTEGER DEFAULT 0
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
    media_type      TEXT CHECK(media_type IN ('photo', 'video') OR media_type IS NULL),
    media_file_id   TEXT,
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

CREATE TABLE IF NOT EXISTS staff_activities (
    user_id             INTEGER PRIMARY KEY,
    activity_count      INTEGER NOT NULL DEFAULT 0,
    earned_points       REAL NOT NULL DEFAULT 0,
    earned_tickets      REAL NOT NULL DEFAULT 0,
    last_activity_at    TEXT,
    updated_at          TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS treasury (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    code        TEXT NOT NULL UNIQUE,
    name        TEXT NOT NULL,
    emoji       TEXT NOT NULL,
    is_general  INTEGER NOT NULL DEFAULT 0 CHECK(is_general IN (0, 1)),
    created_at  TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS treasury_balances (
    treasury_id    INTEGER NOT NULL,
    currency_type  TEXT NOT NULL,
    amount         REAL NOT NULL DEFAULT 0 CHECK(amount >= 0),
    updated_at     TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (treasury_id, currency_type),
    FOREIGN KEY (treasury_id) REFERENCES treasury(id)
);

CREATE TABLE IF NOT EXISTS treasury_members (
    treasury_id  INTEGER NOT NULL,
    user_id      INTEGER NOT NULL UNIQUE,
    assigned_by  INTEGER NOT NULL,
    assigned_at  TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (treasury_id, user_id),
    FOREIGN KEY (treasury_id) REFERENCES treasury(id),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS treasury_transactions (
    id                       INTEGER PRIMARY KEY AUTOINCREMENT,
    treasury_id              INTEGER NOT NULL,
    operation_type           TEXT NOT NULL CHECK(operation_type IN ('donation', 'manual_deposit', 'expense', 'distribution_out', 'distribution_in', 'staff_payout')),
    currency_type            TEXT NOT NULL,
    amount                   REAL NOT NULL CHECK(amount > 0),
    balance_before           REAL NOT NULL,
    balance_after            REAL NOT NULL CHECK(balance_after >= 0),
    related_treasury_id      INTEGER,
    related_user_id          INTEGER,
    initiated_by_telegram_id INTEGER NOT NULL,
    reason                   TEXT DEFAULT '',
    source                   TEXT NOT NULL DEFAULT 'manual',
    request_key              TEXT UNIQUE,
    created_at               TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (treasury_id) REFERENCES treasury(id),
    FOREIGN KEY (related_treasury_id) REFERENCES treasury(id),
    FOREIGN KEY (related_user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS treasury_distribution_settings (
    treasury_id  INTEGER PRIMARY KEY,
    percentage   REAL NOT NULL CHECK(percentage >= 0 AND percentage <= 100),
    updated_at   TEXT DEFAULT (datetime('now')),
    updated_by   INTEGER,
    FOREIGN KEY (treasury_id) REFERENCES treasury(id)
);
"""


DEFAULT_TREASURIES = [
    ("general", "Общая казна клана", "🌐", 1, None),
    ("main", "Казна Основы", "🏠", 0, 25),
    ("academy", "Казна Академки", "🎓", 0, 15),
    ("events_club", "Казна Ивентного", "🎪", 0, 15),
    ("events", "Казна Событий", "🎉", 0, 10),
    ("veterans", "Казна Ветеранов", "🏆", 0, 10),
    ("tech", "Казна Тех. Админов", "🛠", 0, 10),
    ("commissions", "Казна Комиссий", "💼", 0, 15),
]


DEFAULT_SHOP_SETTINGS = [
    ("withdraw_rate", "9"),
    ("withdraw_min", "50"),
    ("item_bronze_active", "1"),
    ("item_silver_active", "1"),
    ("item_gold_active", "1"),
    ("item_platinum_active", "1"),
    ("item_support_active", "1"),
    ("item_help_active", "1"),
    ("ticket_price_bronze", "1.3"),
    ("ticket_price_silver", "2.5"),
    ("ticket_price_gold", "5.0"),
    ("ticket_price_platinum", "10.0"),
    ("ticket_price_support", "2.5"),
    ("roulette_cost_bronze", "1"),
    ("roulette_cost_silver", "1"),
    ("roulette_cost_gold", "1"),
    ("roulette_cost_platinum", "1"),
    ("roulette_cost_support", "1"),
    ("roulette_cost_help", "1"),
]


async def _table_exists(db: aiosqlite.Connection, name: str) -> bool:
    async with db.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (name,)
    ) as cursor:
        return await cursor.fetchone() is not None


async def _columns(db: aiosqlite.Connection, table: str) -> set[str]:
    async with db.execute(f"PRAGMA table_info({table})") as cursor:
        return {row[1] for row in await cursor.fetchall()}


async def _migrate_currency_tables(db: aiosqlite.Connection) -> None:
    user_columns = await _columns(db, "users")
    additions = {
        "player_tag": "TEXT",
        "club_name": "TEXT",
        "tickets_help": "INTEGER DEFAULT 0",
        "unwarns": "INTEGER DEFAULT 0",
        "unmutes": "INTEGER DEFAULT 0",
        "rubles": "REAL DEFAULT 0",
        "stars": "INTEGER DEFAULT 0",
    }
    for name, definition in additions.items():
        if name not in user_columns:
            await db.execute(f"ALTER TABLE users ADD COLUMN {name} {definition}")

    async with db.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='transactions'"
    ) as cursor:
        row = await cursor.fetchone()
    if row and any(name not in row[0] for name in ("unwarns", "unmutes", "rubles", "stars")):
        await db.execute("ALTER TABLE transactions RENAME TO transactions_old")
        await db.execute("""
            CREATE TABLE transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                currency_type TEXT NOT NULL CHECK(currency_type IN ('points', 'tickets_platinum', 'tickets_gold', 'tickets_silver', 'tickets_bronze', 'tickets_support', 'tickets_help', 'unwarns', 'unmutes', 'rubles', 'stars')),
                operation TEXT NOT NULL CHECK(operation IN ('add', 'subtract', 'set')),
                amount REAL NOT NULL,
                reason TEXT DEFAULT '',
                performed_by INTEGER,
                created_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        await db.execute("""
            INSERT INTO transactions
            SELECT id, user_id, currency_type, operation, amount, reason, performed_by, created_at
            FROM transactions_old
        """)
        await db.execute("DROP TABLE transactions_old")

    request_columns = await _columns(db, "requests")
    if "media_type" not in request_columns:
        await db.execute("ALTER TABLE requests ADD COLUMN media_type TEXT")
    if "media_file_id" not in request_columns:
        await db.execute("ALTER TABLE requests ADD COLUMN media_file_id TEXT")

    async with db.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='requests'"
    ) as cursor:
        row = await cursor.fetchone()
    if row and "tickets_help" not in row[0]:
        await db.execute("ALTER TABLE requests RENAME TO requests_old")
        await db.execute("""
            CREATE TABLE requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                currency_type TEXT NOT NULL CHECK(currency_type IN ('points', 'tickets_platinum', 'tickets_gold', 'tickets_silver', 'tickets_bronze', 'tickets_support', 'tickets_help')),
                amount REAL NOT NULL,
                reason TEXT NOT NULL,
                media_type TEXT CHECK(media_type IN ('photo', 'video') OR media_type IS NULL),
                media_file_id TEXT,
                status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'approved', 'rejected')),
                created_at TEXT DEFAULT (datetime('now')),
                reviewed_at TEXT,
                reviewed_by INTEGER,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        await db.execute("""
            INSERT INTO requests (
                id, user_id, currency_type, amount, reason, media_type,
                media_file_id, status, created_at, reviewed_at, reviewed_by
            )
            SELECT id, user_id, currency_type, amount, reason, media_type,
                   media_file_id, status, created_at, reviewed_at, reviewed_by
            FROM requests_old
        """)
        await db.execute("DROP TABLE requests_old")


async def _migrate_old_staff_system(db: aiosqlite.Connection) -> None:
    if await _table_exists(db, "quest_assignments") and await _table_exists(db, "quests"):
        assignment_columns = await _columns(db, "quest_assignments")
        paid_amount = (
            "COALESCE(qa.paid_amount, q.reward_amount)"
            if "paid_amount" in assignment_columns else "q.reward_amount"
        )
        await db.execute(f"""
            INSERT OR IGNORE INTO staff_activities (
                user_id, activity_count, earned_points, earned_tickets, last_activity_at
            )
            SELECT
                qa.user_id,
                COUNT(*),
                COALESCE(SUM(CASE WHEN q.reward_type = 'points'
                    THEN {paid_amount} ELSE 0 END), 0),
                COALESCE(SUM(CASE WHEN q.reward_type LIKE 'tickets_%'
                    THEN {paid_amount} ELSE 0 END), 0),
                MAX(qa.reviewed_at)
            FROM quest_assignments qa
            JOIN quests q ON q.id = qa.quest_id
            WHERE qa.status = 'approved'
            GROUP BY qa.user_id
        """)

    if await _table_exists(db, "staff"):
        staff_columns = await _columns(db, "staff")
        if "rank" in staff_columns or "category_id" in staff_columns:
            await db.execute("ALTER TABLE staff RENAME TO staff_old")
            await db.execute("""
                CREATE TABLE staff (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL UNIQUE,
                    granted_by INTEGER,
                    granted_at TEXT DEFAULT (datetime('now')),
                    is_active INTEGER DEFAULT 1,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            """)
            await db.execute("""
                INSERT INTO staff (id, user_id, granted_by, granted_at, is_active)
                SELECT id, user_id, granted_by, granted_at, is_active FROM staff_old
            """)
            await db.execute("DROP TABLE staff_old")

    await db.execute("DROP INDEX IF EXISTS idx_quest_assignments_active_user")
    for table in (
        "staff_category_operation_items",
        "staff_category_operations",
        "staff_categories",
        "staff_rank_history",
        "staff_rank_coefficients",
        "quest_assignments",
        "quests",
    ):
        await db.execute(f"DROP TABLE IF EXISTS {table}")
    await db.execute("DELETE FROM shop_settings WHERE key = 'migration_v3_ranks_split'")


async def _migrate_old_treasury(db: aiosqlite.Connection) -> None:
    if not await _table_exists(db, "treasury_balances"):
        return
    balance_columns = await _columns(db, "treasury_balances")
    if "treasury_id" in balance_columns:
        return

    await db.execute("ALTER TABLE treasury_balances RENAME TO treasury_balances_old")
    if await _table_exists(db, "treasury_transactions"):
        await db.execute("ALTER TABLE treasury_transactions RENAME TO treasury_transactions_old")
    await db.executescript(CREATE_TABLES_SQL)
    general_id = await _get_treasury_id(db, "general")
    await db.execute("""
        INSERT INTO treasury_balances (treasury_id, currency_type, amount, updated_at)
        SELECT ?, currency_type, amount, updated_at FROM treasury_balances_old
    """, (general_id,))

    if await _table_exists(db, "treasury_transactions_old"):
        await db.execute("""
            INSERT INTO treasury_transactions (
                treasury_id, operation_type, currency_type, amount,
                balance_before, balance_after, related_user_id,
                initiated_by_telegram_id, reason, source, request_key, created_at
            )
            SELECT ?, operation_type, currency_type, amount,
                   balance_before, balance_after, related_user_id,
                   initiated_by_telegram_id, reason,
                   CASE WHEN operation_type = 'donation' THEN 'donation' ELSE 'legacy' END,
                   request_key, created_at
            FROM treasury_transactions_old
        """, (general_id,))
        await db.execute("DROP TABLE treasury_transactions_old")
    await db.execute("DROP TABLE treasury_balances_old")


async def _get_treasury_id(db: aiosqlite.Connection, code: str) -> int:
    async with db.execute("SELECT id FROM treasury WHERE code = ?", (code,)) as cursor:
        row = await cursor.fetchone()
        if not row:
            raise RuntimeError(f"Кзна {code} не создана")
        return row[0]


async def _seed_treasuries(db: aiosqlite.Connection) -> None:
    for code, name, emoji, is_general, percentage in DEFAULT_TREASURIES:
        await db.execute(
            """INSERT OR IGNORE INTO treasury (code, name, emoji, is_general)
               VALUES (?, ?, ?, ?)""",
            (code, name, emoji, is_general),
        )
        if percentage is not None:
            treasury_id = await _get_treasury_id(db, code)
            await db.execute(
                """INSERT OR IGNORE INTO treasury_distribution_settings
                   (treasury_id, percentage) VALUES (?, ?)""",
                (treasury_id, percentage),
            )


async def init_db() -> None:
    """Создать схему и выполнить совместимые миграции."""
    db_dir = os.path.dirname(config.database_path)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)

    async with aiosqlite.connect(config.database_path) as db:
        await db.executescript(CREATE_TABLES_SQL)
        await _migrate_currency_tables(db)
        await _seed_treasuries(db)
        await _migrate_old_treasury(db)
        await _seed_treasuries(db)
        await _migrate_old_staff_system(db)

        for key, value in DEFAULT_SHOP_SETTINGS:
            await db.execute(
                "INSERT OR IGNORE INTO shop_settings (key, value) VALUES (?, ?)",
                (key, value),
            )

        await db.executescript("""
            CREATE INDEX IF NOT EXISTS idx_treasury_transactions_history
            ON treasury_transactions (treasury_id, created_at DESC, id DESC);
            CREATE INDEX IF NOT EXISTS idx_treasury_transactions_user
            ON treasury_transactions (related_user_id, created_at DESC);
        """)
        await db.commit()


def get_db():
    """Получить подключение к базе данных."""
    return aiosqlite.connect(config.database_path)
