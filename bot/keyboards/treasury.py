"""
Клавиатуры казны клуба.
"""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.utils.treasury import TREASURY_CURRENCIES, treasury_currency_button


TICKET_CURRENCIES = [
    "tickets_platinum",
    "tickets_gold",
    "tickets_silver",
    "tickets_bronze",
    "tickets_support",
    "tickets_help",
]


def treasury_main_keyboard(is_owner: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if is_owner:
        builder.row(InlineKeyboardButton(text="🏦 Состояние казны", callback_data="treasury"))
        builder.row(
            InlineKeyboardButton(text="➕ Пополнить", callback_data="treasury_owner_add"),
            InlineKeyboardButton(text="➖ Списать", callback_data="treasury_owner_expense"),
        )
        builder.row(
            InlineKeyboardButton(text="📜 История", callback_data="treasury_history:0"),
            InlineKeyboardButton(text="⚙️ Управление", callback_data="treasury_manage"),
        )
    else:
        builder.row(InlineKeyboardButton(text="❤️ Пожертвовать", callback_data="treasury_donate"))
    builder.row(InlineKeyboardButton(text="⬅️ Главное меню", callback_data="main_menu"))
    return builder.as_markup()


def donation_type_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="⭐ Баллы", callback_data="treasury_donate_currency:points"))
    builder.row(InlineKeyboardButton(text="🎫 Тикеты", callback_data="treasury_donate_tickets"))
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="treasury_cancel"))
    return builder.as_markup()


def donation_ticket_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for currency_type in TICKET_CURRENCIES:
        builder.row(InlineKeyboardButton(
            text=treasury_currency_button(currency_type),
            callback_data=f"treasury_donate_currency:{currency_type}",
        ))
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="treasury_donate"))
    return builder.as_markup()


def treasury_cancel_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="treasury_cancel"))
    return builder.as_markup()


def donation_confirm_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Пожертвовать", callback_data="treasury_donate_confirm"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="treasury_cancel"),
    )
    return builder.as_markup()


def owner_currency_keyboard(operation_type: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    currencies = list(TREASURY_CURRENCIES)
    for index in range(0, len(currencies), 2):
        buttons = []
        for currency_type in currencies[index:index + 2]:
            buttons.append(InlineKeyboardButton(
                text=treasury_currency_button(currency_type),
                callback_data=f"treasury_owner_currency:{operation_type}:{currency_type}",
            ))
        builder.row(*buttons)
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="treasury_cancel"))
    return builder.as_markup()


def owner_reason_keyboard(can_skip: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if can_skip:
        builder.row(InlineKeyboardButton(text="⏭ Без комментария", callback_data="treasury_reason_skip"))
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="treasury_cancel"))
    return builder.as_markup()


def owner_confirm_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Подтвердить", callback_data="treasury_owner_confirm"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="treasury_cancel"),
    )
    return builder.as_markup()


def treasury_history_keyboard(offset: int, total: int, page_size: int = 8) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    buttons = []
    if offset > 0:
        buttons.append(InlineKeyboardButton(
            text="◀️ Назад",
            callback_data=f"treasury_history:{max(0, offset - page_size)}",
        ))
    if offset + page_size < total:
        buttons.append(InlineKeyboardButton(
            text="▶️ Вперёд",
            callback_data=f"treasury_history:{offset + page_size}",
        ))
    if buttons:
        builder.row(*buttons)
    builder.row(InlineKeyboardButton(text="⬅️ К казне", callback_data="treasury"))
    return builder.as_markup()


def treasury_manage_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="➕ Пополнить", callback_data="treasury_owner_add"),
        InlineKeyboardButton(text="➖ Списать", callback_data="treasury_owner_expense"),
    )
    builder.row(InlineKeyboardButton(text="📜 История", callback_data="treasury_history:0"))
    builder.row(InlineKeyboardButton(text="⬅️ К казне", callback_data="treasury"))
    return builder.as_markup()
