"""Клавиатуры раздела казны."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.utils.treasury import DONATION_CURRENCIES, TREASURY_CURRENCIES, treasury_currency_button


def treasury_list_keyboard(treasuries: list[dict], is_owner: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for item in treasuries:
        builder.row(InlineKeyboardButton(
            text=f"{item['emoji']} {item['name']}",
            callback_data=f"treasury_view:{item['id']}",
        ))
    builder.row(InlineKeyboardButton(text="➕ Пополнить казну", callback_data="treasury_topup"))
    builder.row(InlineKeyboardButton(text="❤️ Пожертвовать", callback_data="treasury_donate"))
    if is_owner:
        builder.row(
            InlineKeyboardButton(text="📊 Распределить баланс", callback_data="treasury_distribute"),
            InlineKeyboardButton(text="⚙️ Проценты казны", callback_data="treasury_percentages"),
        )
    builder.row(InlineKeyboardButton(text="⬅️ Главное меню", callback_data="main_menu"))
    return builder.as_markup()


def treasury_page_keyboard(treasury_id: int, is_owner: bool, is_general: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if is_owner and not is_general:
        builder.row(
            InlineKeyboardButton(text="👥 Участники", callback_data=f"treasury_members:{treasury_id}"),
            InlineKeyboardButton(text="💰 Выдать баллы", callback_data=f"treasury_payout:{treasury_id}"),
        )
    builder.row(
        InlineKeyboardButton(text="➕ Пополнить", callback_data=f"treasury_topup_one:{treasury_id}"),
        InlineKeyboardButton(text="📜 История", callback_data=f"treasury_history:{treasury_id}:0"),
    )
    if is_owner:
        builder.row(InlineKeyboardButton(
            text="➖ Списать", callback_data=f"treasury_spend:{treasury_id}"
        ))
    if is_owner and is_general:
        builder.row(InlineKeyboardButton(
            text="📊 Распределить баланс", callback_data="treasury_distribute"
        ))
    builder.row(InlineKeyboardButton(text="⬅️ Все казны", callback_data="treasury"))
    return builder.as_markup()


def topup_mode_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔘 Пополнить все казны", callback_data="treasury_topup_all"))
    builder.row(InlineKeyboardButton(text="🔘 Пополнить выбранные", callback_data="treasury_topup_selected"))
    builder.row(InlineKeyboardButton(text="🔘 Пополнить одну", callback_data="treasury_topup_single"))
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="treasury_cancel"))
    return builder.as_markup()


def treasury_pick_keyboard(treasuries: list[dict], prefix: str, back: str = "treasury_cancel") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for item in treasuries:
        builder.row(InlineKeyboardButton(
            text=f"{item['emoji']} {item['name']}",
            callback_data=f"{prefix}:{item['id']}",
        ))
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data=back))
    return builder.as_markup()


def treasury_multi_pick_keyboard(treasuries: list[dict], selected: set[int]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for item in treasuries:
        mark = "✅" if item["id"] in selected else "⬜"
        builder.row(InlineKeyboardButton(
            text=f"{mark} {item['emoji']} {item['name']}",
            callback_data=f"treasury_topup_toggle:{item['id']}",
        ))
    builder.row(InlineKeyboardButton(text="➡️ Продолжить", callback_data="treasury_topup_selection_done"))
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="treasury_cancel"))
    return builder.as_markup()


def currency_keyboard(prefix: str, donation_only: bool = False) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    currencies = (
        [currency for currency in TREASURY_CURRENCIES if currency in DONATION_CURRENCIES]
        if donation_only else TREASURY_CURRENCIES.keys()
    )
    for currency_type in currencies:
        builder.row(InlineKeyboardButton(
            text=treasury_currency_button(currency_type),
            callback_data=f"{prefix}:{currency_type}",
        ))
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="treasury_cancel"))
    return builder.as_markup()


def split_mode_keyboard(allow_percent: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="✍️ Сумма для каждой", callback_data="treasury_split:manual"))
    builder.row(InlineKeyboardButton(text="⚖️ Распределить поровну", callback_data="treasury_split:equal"))
    if allow_percent:
        builder.row(InlineKeyboardButton(text="📊 По сохранённым процентам", callback_data="treasury_split:percent"))
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="treasury_cancel"))
    return builder.as_markup()


def confirm_keyboard(confirm_callback: str, confirm_text: str = "✅ Подтвердить") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text=confirm_text, callback_data=confirm_callback),
        InlineKeyboardButton(text="❌ Отмена", callback_data="treasury_cancel"),
    )
    return builder.as_markup()


def distribution_mode_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔘 Весь баланс", callback_data="treasury_dist_all"))
    builder.row(InlineKeyboardButton(text="🔘 Определённую сумму", callback_data="treasury_dist_amount"))
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="treasury_cancel"))
    return builder.as_markup()


def percentages_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="✏️ Изменить проценты", callback_data="treasury_percentages_edit"))
    builder.row(InlineKeyboardButton(text="⬅️ К казнам", callback_data="treasury"))
    return builder.as_markup()


def history_keyboard(treasury_id: int, offset: int, total: int, page_size: int = 8) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    nav = []
    if offset > 0:
        nav.append(InlineKeyboardButton(
            text="◀️ Назад", callback_data=f"treasury_history:{treasury_id}:{max(0, offset - page_size)}"
        ))
    if offset + page_size < total:
        nav.append(InlineKeyboardButton(
            text="▶️ Вперёд", callback_data=f"treasury_history:{treasury_id}:{offset + page_size}"
        ))
    if nav:
        builder.row(*nav)
    builder.row(InlineKeyboardButton(text="⬅️ К казне", callback_data=f"treasury_view:{treasury_id}"))
    return builder.as_markup()


def members_keyboard(treasury_id: int, members: list[dict]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for member in members:
        builder.row(InlineKeyboardButton(
            text=f"🛠 {member['nickname']}",
            callback_data=f"treasury_member:{treasury_id}:{member['user_id']}",
        ))
    builder.row(InlineKeyboardButton(text="➕ Добавить Staff", callback_data=f"treasury_member_add:{treasury_id}"))
    builder.row(InlineKeyboardButton(text="⬅️ К казне", callback_data=f"treasury_view:{treasury_id}"))
    return builder.as_markup()


def member_actions_keyboard(treasury_id: int, user_id: int, telegram_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="👤 Открыть профиль", callback_data=f"staff_view:{telegram_id}"))
    builder.row(InlineKeyboardButton(text="🔄 Перевести", callback_data=f"treasury_member_move:{treasury_id}:{user_id}"))
    builder.row(InlineKeyboardButton(text="➖ Удалить", callback_data=f"treasury_member_remove:{treasury_id}:{user_id}"))
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"treasury_members:{treasury_id}"))
    return builder.as_markup()


def payout_mode_keyboard(treasury_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="👥 Всей казне", callback_data=f"treasury_payout_group:{treasury_id}"))
    builder.row(InlineKeyboardButton(text="👤 Одному человеку", callback_data=f"treasury_payout_one:{treasury_id}"))
    builder.row(InlineKeyboardButton(text="⬅️ К казне", callback_data=f"treasury_view:{treasury_id}"))
    return builder.as_markup()


def payout_member_keyboard(treasury_id: int, members: list[dict]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for member in members:
        builder.row(InlineKeyboardButton(
            text=f"🛠 {member['nickname']}",
            callback_data=f"treasury_payout_user:{treasury_id}:{member['user_id']}",
        ))
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"treasury_payout:{treasury_id}"))
    return builder.as_markup()


def simple_cancel_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="treasury_cancel"))
    return builder.as_markup()
