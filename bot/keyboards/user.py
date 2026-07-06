"""
Клавиатуры для обычных пользователей.
"""

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

# Типы тикетов: (callback_data_suffix, emoji, название, стоимость в баллах)
TICKET_TYPES = [
    ("platinum", "💎", "Платиновый", 10),
    ("gold",     "🥇", "Золотой",    5),
    ("silver",   "🥈", "Серебряный", 2.5),
    ("bronze",   "🥉", "Бронзовый",  1.3),
    ("support",  "🎁", "Вспомогательный", 2.5),
    ("help",     "💪", "Хелп тикет", 0),
]


def main_menu_keyboard(is_owner: bool = False, is_staff: bool = False) -> InlineKeyboardMarkup:
    """Главное меню."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="👤 Мой профиль", callback_data="profile"))
    builder.row(
        InlineKeyboardButton(text="🎫 Тикеты", callback_data="tickets_menu"),
        InlineKeyboardButton(text="⭐ Баллы",   callback_data="points_menu"),
    )
    builder.row(InlineKeyboardButton(text="🛒 Магазин", callback_data="shop_main"))
    if is_staff and not is_owner:
        builder.row(
            InlineKeyboardButton(text="📋 Квесты", callback_data="staff_quests_menu"),
            InlineKeyboardButton(text="🎖 Роль",   callback_data="staff_role"),
        )
    if is_owner:
        builder.row(InlineKeyboardButton(text="👑 Админ-панель", callback_data="admin_panel"))
    return builder.as_markup()


def tickets_menu_keyboard() -> InlineKeyboardMarkup:
    """Меню раздела Тикеты."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📨 Запросить тикет", callback_data="request_tickets"))
    builder.row(InlineKeyboardButton(text="📊 История тикетов", callback_data="history_tickets:0"))
    builder.row(InlineKeyboardButton(text="⬅️ Главное меню", callback_data="main_menu"))
    return builder.as_markup()


def points_menu_keyboard() -> InlineKeyboardMarkup:
    """Меню раздела Баллы."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📨 Запросить баллы", callback_data="request_points"))
    builder.row(InlineKeyboardButton(text="📊 История баллов", callback_data="history_points:0"))
    builder.row(InlineKeyboardButton(text="⬅️ Главное меню", callback_data="main_menu"))
    return builder.as_markup()


def ticket_type_keyboard() -> InlineKeyboardMarkup:
    """Выбор типа тикета."""
    builder = InlineKeyboardBuilder()
    for key, emoji, name, value in TICKET_TYPES:
        if key == "help":
            builder.row(InlineKeyboardButton(
                text=f"{emoji} {name}",
                callback_data=f"ticket_type:{key}"
            ))
        else:
            builder.row(InlineKeyboardButton(
                text=f"{emoji} {name} ({value:g} балл{'а' if value < 2 or 2 <= value < 5 else 'ов'})",
                callback_data=f"ticket_type:{key}"
            ))
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_form"))
    return builder.as_markup()


def currency_menu_keyboard() -> InlineKeyboardMarkup:
    """Меню раздела Баллы / Тикеты (оставлено для совместимости)."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📊 История операций", callback_data="history:0"))
    builder.row(InlineKeyboardButton(text="📨 Запросить тикеты", callback_data="request_tickets"))
    builder.row(InlineKeyboardButton(text="📨 Запросить баллы", callback_data="request_points"))
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="main_menu"))
    return builder.as_markup()


def back_to_main_keyboard() -> InlineKeyboardMarkup:
    """Кнопка «Назад в главное меню»."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="⬅️ Главное меню", callback_data="main_menu"))
    return builder.as_markup()


def back_to_tickets_keyboard() -> InlineKeyboardMarkup:
    """Кнопка «Назад в меню тикетов»."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="tickets_menu"))
    return builder.as_markup()


def back_to_points_keyboard() -> InlineKeyboardMarkup:
    """Кнопка «Назад в меню баллов»."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="points_menu"))
    return builder.as_markup()


def back_to_currency_keyboard() -> InlineKeyboardMarkup:
    """Кнопка «Назад к меню валют»."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="currency_menu"))
    return builder.as_markup()


def history_navigation_keyboard(offset: int, total: int, page_size: int = 5) -> InlineKeyboardMarkup:
    """Навигация по истории операций."""
    builder = InlineKeyboardBuilder()
    nav_row = []

    if offset > 0:
        nav_row.append(InlineKeyboardButton(
            text="◀️ Назад",
            callback_data=f"history:{max(0, offset - page_size)}"
        ))

    if offset + page_size < total:
        nav_row.append(InlineKeyboardButton(
            text="▶️ Вперёд",
            callback_data=f"history:{offset + page_size}"
        ))

    if nav_row:
        builder.row(*nav_row)

    builder.row(InlineKeyboardButton(text="⬅️ В меню", callback_data="currency_menu"))
    return builder.as_markup()


def history_tickets_nav_keyboard(offset: int, total: int, page_size: int = 5) -> InlineKeyboardMarkup:
    """Навигация по истории тикетов."""
    builder = InlineKeyboardBuilder()
    nav_row = []

    if offset > 0:
        nav_row.append(InlineKeyboardButton(
            text="◀️ Назад",
            callback_data=f"history_tickets:{max(0, offset - page_size)}"
        ))

    if offset + page_size < total:
        nav_row.append(InlineKeyboardButton(
            text="▶️ Вперёд",
            callback_data=f"history_tickets:{offset + page_size}"
        ))

    if nav_row:
        builder.row(*nav_row)

    builder.row(InlineKeyboardButton(text="⬅️ К тикетам", callback_data="tickets_menu"))
    return builder.as_markup()


def history_points_nav_keyboard(offset: int, total: int, page_size: int = 5) -> InlineKeyboardMarkup:
    """Навигация по истории баллов."""
    builder = InlineKeyboardBuilder()
    nav_row = []

    if offset > 0:
        nav_row.append(InlineKeyboardButton(
            text="◀️ Назад",
            callback_data=f"history_points:{max(0, offset - page_size)}"
        ))

    if offset + page_size < total:
        nav_row.append(InlineKeyboardButton(
            text="▶️ Вперёд",
            callback_data=f"history_points:{offset + page_size}"
        ))

    if nav_row:
        builder.row(*nav_row)

    builder.row(InlineKeyboardButton(text="⬅️ К баллам", callback_data="points_menu"))
    return builder.as_markup()


def cancel_keyboard() -> InlineKeyboardMarkup:
    """Кнопка отмены FSM-формы."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_form"))
    return builder.as_markup()


def registration_keyboard() -> InlineKeyboardMarkup:
    """Кнопка регистрации."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📝 Регистрация", callback_data="start_registration"))
    return builder.as_markup()


#  МАГАЗИН

# Рулетки: (ключ, эмодзи, название, соответствующий тип тикета)
ROULETTE_ITEMS = [
    ("platinum", "💎", "Платиновая рулетка",      "tickets_platinum"),
    ("gold",     "🥇", "Золотая рулетка",         "tickets_gold"),
    ("silver",   "🥈", "Серебряная рулетка",      "tickets_silver"),
    ("bronze",   "🥉", "Бронзовая рулетка",       "tickets_bronze"),
    ("support",  "🎁", "Вспомогательная рулетка", "tickets_support"),
    ("help",     "💪", "Хелп рулетка",            "tickets_help"),
]


def shop_main_keyboard() -> InlineKeyboardMarkup:
    """Главное меню магазина."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🎫 Магазин за тикеты", callback_data="shop_tickets"))
    builder.row(InlineKeyboardButton(text="⭐ Магазин за баллы",  callback_data="shop_points"))
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="main_menu"))
    return builder.as_markup()


def shop_tickets_keyboard(settings: dict) -> InlineKeyboardMarkup:
    """Список рулеток за тикеты."""
    builder = InlineKeyboardBuilder()
    for key, emoji, name, ticket_type in ROULETTE_ITEMS:
        active = settings.get(f"item_{key}_active", "1") == "1"
        cost = int(float(settings.get(f"roulette_cost_{key}", "1")))
        ticket_key = ticket_type.replace("tickets_", "")
        ticket_emoji, ticket_name = TICKET_NAMES_SHORT.get(ticket_key, ("🎫", ticket_key))
        label = f"{emoji} {name} — {cost} {ticket_name} тикет"
        if not active:
            label = f"🚫 {name} (недоступно)"
        builder.row(InlineKeyboardButton(
            text=label,
            callback_data=f"shop_buy:{key}" if active else "shop_unavailable"
        ))
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="shop_main"))
    return builder.as_markup()


def confirm_purchase_keyboard(item_key: str) -> InlineKeyboardMarkup:
    """Подтверждение покупки рулетки."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Да",  callback_data=f"shop_confirm:{item_key}"),
        InlineKeyboardButton(text="❌ Нет", callback_data="shop_tickets"),
    )
    return builder.as_markup()


def shop_points_keyboard() -> InlineKeyboardMarkup:
    """Меню магазина за баллы."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🎫 Обмен баллов на тикеты", callback_data="shop_exchange"))
    builder.row(InlineKeyboardButton(text="💰 Вывод баллов в деньги",  callback_data="shop_withdraw"))
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="shop_main"))
    return builder.as_markup()


def shop_exchange_ticket_keyboard() -> InlineKeyboardMarkup:
    """Выбор типа тикета для обмена баллов."""
    builder = InlineKeyboardBuilder()
    for key, emoji, name, value in TICKET_TYPES:
        if key == "help":
            continue
        builder.row(InlineKeyboardButton(
            text=f"{emoji} {name} — {value:g} баллов",
            callback_data=f"shop_exch_type:{key}"
        ))
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="shop_points"))
    return builder.as_markup()


def confirm_exchange_keyboard() -> InlineKeyboardMarkup:
    """Подтверждение обмена баллов на тикеты."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Да",  callback_data="shop_exch_confirm"),
        InlineKeyboardButton(text="❌ Нет", callback_data="shop_exchange"),
    )
    return builder.as_markup()


def confirm_withdraw_keyboard() -> InlineKeyboardMarkup:
    """Подтверждение вывода баллов."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Да",  callback_data="shop_withdraw_confirm"),
        InlineKeyboardButton(text="❌ Нет", callback_data="shop_withdraw"),
    )
    return builder.as_markup()


def contact_owner_keyboard(owner_id: int, owner_username: str = None) -> InlineKeyboardMarkup:
    """Кнопка «Написать владельцу»."""
    builder = InlineKeyboardBuilder()
    url = f"https://t.me/{owner_username}" if owner_username else f"tg://user?id={owner_id}"
    builder.row(InlineKeyboardButton(
        text="📩 Написать владельцу",
        url=url
    ))
    return builder.as_markup()


def back_to_shop_keyboard() -> InlineKeyboardMarkup:
    """Назад в главное меню магазина."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="⬅️ В магазин", callback_data="shop_main"))
    return builder.as_markup()


# Краткие названия тикетов для магазина
TICKET_NAMES_SHORT = {
    "platinum": ("💎", "Платиновый"),
    "gold":     ("🥇", "Золотой"),
    "silver":   ("🥈", "Серебряный"),
    "bronze":   ("🥉", "Бронзовый"),
    "support":  ("🎁", "Вспомогательный"),
    "help":     ("💪", "Хелп"),
}


