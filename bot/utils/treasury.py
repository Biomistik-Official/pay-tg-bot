"""
Метаданны и форматирование средств казны.
"""

from bot.utils.formatters import TICKET_NAMES


TREASURY_CURRENCIES = {
    "points": {"emoji": "⭐", "name": "Баллы", "integer": False},
    "tickets_platinum": {"emoji": "💎", "name": "Платиновые тикеты", "integer": True},
    "tickets_gold": {"emoji": "🥇", "name": "Золотые тикеты", "integer": True},
    "tickets_silver": {"emoji": "🥈", "name": "Серебряные тикеты", "integer": True},
    "tickets_bronze": {"emoji": "🥉", "name": "Бронзовые тикеты", "integer": True},
    "tickets_support": {"emoji": "🎁", "name": "Вспомогательные тикеты", "integer": True},
    "tickets_help": {"emoji": "💪", "name": "Хелп тикеты", "integer": True},
    "rubles": {"emoji": "💰", "name": "Рубли", "integer": False},
    "stars": {"emoji": "🌟", "name": "Звёзды", "integer": True},
    "unwarns": {"emoji": "⚠️", "name": "Анварны", "integer": True},
    "unmutes": {"emoji": "🔇", "name": "Анмуты", "integer": True},
}

DONATION_CURRENCIES = {
    "points",
    "tickets_platinum",
    "tickets_gold",
    "tickets_silver",
    "tickets_bronze",
    "tickets_support",
    "tickets_help",
}


def format_treasury_amount(currency_type: str, amount: float) -> str:
    meta = TREASURY_CURRENCIES.get(
        currency_type,
        {"emoji": "💳", "name": currency_type, "integer": False},
    )
    value = str(int(amount)) if meta["integer"] else f"{amount:g}"

    if currency_type == "points":
        return f"⭐ {value} баллов"
    if currency_type.startswith("tickets_"):
        key = currency_type.removeprefix("tickets_")
        emoji, name = TICKET_NAMES.get(key, ("🎫", "Тикет"))
        return f"{emoji} {value} шт. ({name} тикет)"
    if currency_type == "rubles":
        return f"💰 {value} ₽"
    if currency_type == "stars":
        return f"🌟 {value} шт."
    if currency_type == "unwarns":
        return f"⚠️ {value} анварнов"
    if currency_type == "unmutes":
        return f"🔇 {value} анмутов"
    return f"{meta['emoji']} {value} {meta['name']}"


def treasury_currency_button(currency_type: str) -> str:
    meta = TREASURY_CURRENCIES[currency_type]
    return f"{meta['emoji']} {meta['name']}"
