"""
Клавиатуры для Staff (раздел Квестов).
"""

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def staff_quests_main_keyboard() -> InlineKeyboardMarkup:
    """Главное меню квестов для Staff."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🟢 Активные квесты", callback_data="staff_active_quests:0"))
    builder.row(InlineKeyboardButton(text="🟡 Мои квесты",       callback_data="staff_my_quests"))
    builder.row(InlineKeyboardButton(text="📜 История",           callback_data="staff_quest_history"))
    builder.row(InlineKeyboardButton(text="⬅️ Главное меню",      callback_data="main_menu"))
    return builder.as_markup()


def active_quests_keyboard(quests: list[dict], offset: int, total: int, page_size: int = 5) -> InlineKeyboardMarkup:
    """Список активных квестов с навигацией."""
    builder = InlineKeyboardBuilder()
    for q in quests:
        title = q["title"][:22] + "..." if len(q["title"]) > 22 else q["title"]
        builder.row(InlineKeyboardButton(
            text=f"🟢 {title}",
            callback_data=f"staff_quest_detail:{q['id']}"
        ))
    nav = []
    if offset > 0:
        nav.append(InlineKeyboardButton(text="◀️ Назад", callback_data=f"staff_active_quests:{offset - page_size}"))
    if offset + page_size < total:
        nav.append(InlineKeyboardButton(text="▶️ Вперёд", callback_data=f"staff_active_quests:{offset + page_size}"))
    if nav:
        builder.row(*nav)
    builder.row(InlineKeyboardButton(text="⬅️ К квестам", callback_data="staff_quests_menu"))
    return builder.as_markup()


def quest_detail_staff_keyboard(quest_id: int, can_take: bool, already_taken: bool) -> InlineKeyboardMarkup:
    """Детали квеста для Staff."""
    builder = InlineKeyboardBuilder()
    if already_taken:
        builder.row(InlineKeyboardButton(text="✅ Уже взято вами", callback_data="staff_quest_noop"))
    elif can_take:
        builder.row(InlineKeyboardButton(text="✅ Взять квест", callback_data=f"staff_take_quest:{quest_id}"))
    else:
        builder.row(InlineKeyboardButton(text="❌ Набор завершён", callback_data="staff_quest_noop"))
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="staff_active_quests:0"))
    return builder.as_markup()


def my_quests_keyboard(assignments: list[dict]) -> InlineKeyboardMarkup:
    """Список активных квестов пользователя."""
    builder = InlineKeyboardBuilder()
    for a in assignments:
        title = a["title"][:20] + "..." if len(a["title"]) > 20 else a["title"]
        status_icon = "🟡" if a["status"] == "taken" else "⏳"
        builder.row(InlineKeyboardButton(
            text=f"{status_icon} {title}",
            callback_data=f"staff_my_quest_detail:{a['id']}"
        ))
    if not assignments:
        builder.row(InlineKeyboardButton(text="📋 Нет активных квестов", callback_data="staff_quest_noop"))
    builder.row(InlineKeyboardButton(text="⬅️ К квестам", callback_data="staff_quests_menu"))
    return builder.as_markup()


def quest_submit_keyboard(assignment_id: int) -> InlineKeyboardMarkup:
    """Отправить квест на проверку."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="📨 Отправить на проверку",
        callback_data=f"staff_submit_quest:{assignment_id}"
    ))
    builder.row(InlineKeyboardButton(
        text="❌ Отказаться от квеста",
        callback_data=f"staff_abandon_quest:{assignment_id}"
    ))
    builder.row(InlineKeyboardButton(text="⬅️ Мои квесты", callback_data="staff_my_quests"))
    return builder.as_markup()


def quest_submitted_keyboard() -> InlineKeyboardMarkup:
    """После отправки квеста."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🟡 Мои квесты", callback_data="staff_my_quests"))
    builder.row(InlineKeyboardButton(text="⬅️ Главное меню", callback_data="main_menu"))
    return builder.as_markup()


def quest_history_keyboard(history: list[dict]) -> InlineKeyboardMarkup:
    """История квестов пользователя."""
    builder = InlineKeyboardBuilder()
    for h in history:
        title = h["title"][:18] + "..." if len(h["title"]) > 18 else h["title"]
        if h["status"] == "approved":
            icon = "🟢"
        elif h["status"] == "rejected":
            icon = "🔴"
        else:
            icon = "🟡"
        builder.row(InlineKeyboardButton(
            text=f"{icon} {title}",
            callback_data=f"staff_history_detail:{h['id']}"
        ))
    if not history:
        builder.row(InlineKeyboardButton(text="📜 История пуста", callback_data="staff_quest_noop"))
    builder.row(InlineKeyboardButton(text="⬅️ К квестам", callback_data="staff_quests_menu"))
    return builder.as_markup()


def submit_content_keyboard(assignment_id: int) -> InlineKeyboardMarkup:
    """После отправки материала — подтверждение."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"staff_submit_confirm:{assignment_id}"),
        InlineKeyboardButton(text="✏️ Изменить",   callback_data=f"staff_submit_quest:{assignment_id}"),
    )
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="staff_my_quests"))
    return builder.as_markup()


def cancel_staff_keyboard() -> InlineKeyboardMarkup:
    """Кнопка отмены для Staff FSM."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="staff_quests_menu"))
    return builder.as_markup()
