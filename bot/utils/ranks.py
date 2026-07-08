"""
Ранги Staff и коэффициенты наград — внутренняя система Telegram-бота.

Ранг НЕ связан с Brawl Stars. Изменять ранг может только Owner.
Метаданные рангов (эмодзи, название, описание) — константы здесь,
коэффициенты хранятся в таблице staff_rank_coefficients (редактируются Owner).
"""

# Порядок рангов от высшего к низшему
RANK_ORDER = ["grand", "vice", "helper", "novice"]

# Ранг по умолчанию для нового Staff
DEFAULT_RANK = "novice"

# Метаданные рангов
RANK_META = {
    "grand": {
        "emoji": "🥇",
        "name": "Гранд",
        "default_coef":     1.5,   # квест-коэффициент
        "default_cat_coef": 1.0,   # категор.-коэффициент
        "description": "Высший ранг Staff. Максимальное доверие, ответственность и полномочия.",
    },
    "vice": {
        "emoji": "🥈",
        "name": "Вице",
        "default_coef":     1.3,
        "default_cat_coef": 0.5,
        "description": "Заместитель. Высокий уровень доверия и расширенные полномочия.",
    },
    "helper": {
        "emoji": "🥉",
        "name": "Помощник",
        "default_coef":     1.1,
        "default_cat_coef": 0.25,
        "description": "Опытный участник команды, активно помогает в задачах.",
    },
    "novice": {
        "emoji": "🎓",
        "name": "Новобранец",
        "default_coef":     1.0,
        "default_cat_coef": 0.0,
        "description": "Начальный ранг. Добро пожаловать в команду Staff!",
    },
}


def rank_emoji(rank: str) -> str:
    """Эмодзи ранга."""
    return RANK_META.get(rank, RANK_META[DEFAULT_RANK])["emoji"]


def rank_name(rank: str) -> str:
    """Читаемое название ранга."""
    return RANK_META.get(rank, RANK_META[DEFAULT_RANK])["name"]


def rank_label(rank: str) -> str:
    """Эмодзи + название ранга (например «🥇 Гранд»)."""
    meta = RANK_META.get(rank, RANK_META[DEFAULT_RANK])
    return f"{meta['emoji']} {meta['name']}"


def rank_description(rank: str) -> str:
    """Описание ранга."""
    return RANK_META.get(rank, RANK_META[DEFAULT_RANK])["description"]


def apply_coefficient(reward_type: str, base_amount: float, coef: float) -> float:
    """
    Рассчитать итоговую награду с учётом коэффициента ранга.

    Баллы (points) — REAL, округляем до 2 знаков.
    Тикеты — INTEGER, округляем до целого.
    """
    result = base_amount * coef
    if reward_type == "points":
        return round(result, 2)
    return float(round(result))
