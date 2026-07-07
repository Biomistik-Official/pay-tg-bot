"""
Клавиатуры для раздела «Категории Staff» (Owner only).
"""

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def categories_menu_keyboard(categories: list[dict]) -> InlineKeyboardMarkup:
    """Главное меню категорий: список + создать."""
    builder = InlineKeyboardBuilder()
    for c in categories:
        builder.row(InlineKeyboardButton(
            text=f"{c['name']} — ×{c['coefficient']:g} · {c['members_count']}👥",
            callback_data=f"cat_view:{c['id']}",
        ))
    builder.row(InlineKeyboardButton(text="➕ Создать категорию", callback_data="cat_create"))
    builder.row(InlineKeyboardButton(text="⬅️ Управление Staff", callback_data="admin_staff"))
    return builder.as_markup()


def category_detail_keyboard(category_id: int) -> InlineKeyboardMarkup:
    """Экран одной категории."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="👥 Участники",  callback_data=f"cat_members:{category_id}"),
        InlineKeyboardButton(text="📊 Статистика", callback_data=f"cat_stats:{category_id}"),
    )
    builder.row(
        InlineKeyboardButton(text="💰 Выдать зарплату",         callback_data=f"cat_salary:{category_id}"),
        InlineKeyboardButton(text="👤 Зарплата сотруднику",     callback_data=f"cat_salary_one:{category_id}"),
    )
    builder.row(
        InlineKeyboardButton(text="⚠️ Штраф",                    callback_data=f"cat_penalty:{category_id}"),
        InlineKeyboardButton(text="📢 Сообщение категории",      callback_data=f"cat_broadcast:{category_id}"),
    )
    builder.row(
        InlineKeyboardButton(text="📜 История начислений",       callback_data=f"cat_history:{category_id}"),
    )
    builder.row(
        InlineKeyboardButton(text="✏️ Изменить",  callback_data=f"cat_edit:{category_id}"),
        InlineKeyboardButton(text="🗑 Удалить",   callback_data=f"cat_delete:{category_id}"),
    )
    builder.row(InlineKeyboardButton(text="⬅️ К списку категорий", callback_data="admin_cats"))
    return builder.as_markup()


def category_edit_field_keyboard(category_id: int) -> InlineKeyboardMarkup:
    """Выбор поля для редактирования."""
    builder = InlineKeyboardBuilder()
    fields = [
        ("name",        "📌 Название"),
        ("description", "📝 Описание"),
        ("coefficient", "📈 Коэффициент"),
        ("comment",     "💬 Комментарий"),
    ]
    for key, label in fields:
        builder.row(InlineKeyboardButton(
            text=label,
            callback_data=f"cat_edit_field:{category_id}:{key}",
        ))
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"cat_view:{category_id}"))
    return builder.as_markup()


def category_delete_confirm_keyboard(category_id: int) -> InlineKeyboardMarkup:
    """Подтверждение удаления."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"cat_delete_confirm:{category_id}"),
        InlineKeyboardButton(text="❌ Отмена",       callback_data=f"cat_view:{category_id}"),
    )
    return builder.as_markup()


def category_members_keyboard(category_id: int, members: list[dict]) -> InlineKeyboardMarkup:
    """Список участников категории."""
    from bot.utils.ranks import rank_emoji, DEFAULT_RANK
    builder = InlineKeyboardBuilder()
    for m in members:
        r = m.get("rank") or DEFAULT_RANK
        nick = m["nickname"]
        if len(nick) > 15:
            nick = nick[:12] + "..."
        builder.row(InlineKeyboardButton(
            text=f"{rank_emoji(r)} {nick}",
            callback_data=f"cat_member:{category_id}:{m['telegram_id']}",
        ))
    builder.row(InlineKeyboardButton(
        text="➕ Добавить Staff",
        callback_data=f"cat_add_member:{category_id}",
    ))
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"cat_view:{category_id}"))
    return builder.as_markup()


def category_member_actions_keyboard(category_id: int, telegram_id: int) -> InlineKeyboardMarkup:
    """Действия с сотрудником в категории."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="👤 Профиль",
        callback_data=f"staff_view:{telegram_id}",
    ))
    builder.row(InlineKeyboardButton(
        text="🔄 Перевести в другую категорию",
        callback_data=f"cat_move:{category_id}:{telegram_id}",
    ))
    builder.row(InlineKeyboardButton(
        text="➖ Удалить из категории",
        callback_data=f"cat_kick:{category_id}:{telegram_id}",
    ))
    builder.row(InlineKeyboardButton(
        text="⬅️ К участникам",
        callback_data=f"cat_members:{category_id}",
    ))
    return builder.as_markup()


def category_add_member_keyboard(category_id: int, staff_list: list[dict]) -> InlineKeyboardMarkup:
    """Список Staff без категории (для добавления)."""
    from bot.utils.ranks import rank_emoji, DEFAULT_RANK
    builder = InlineKeyboardBuilder()
    for m in staff_list:
        r = m.get("rank") or DEFAULT_RANK
        nick = m["nickname"]
        if len(nick) > 15:
            nick = nick[:12] + "..."
        builder.row(InlineKeyboardButton(
            text=f"{rank_emoji(r)} {nick}",
            callback_data=f"cat_add_pick:{category_id}:{m['telegram_id']}",
        ))
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"cat_members:{category_id}"))
    return builder.as_markup()


def category_move_keyboard(target_categories: list[dict], telegram_id: int) -> InlineKeyboardMarkup:
    """Куда перевести сотрудника."""
    builder = InlineKeyboardBuilder()
    for c in target_categories:
        builder.row(InlineKeyboardButton(
            text=f"➡️ {c['name']}",
            callback_data=f"cat_move_to:{c['id']}:{telegram_id}",
        ))
    builder.row(InlineKeyboardButton(
        text="🚫 Убрать из категории",
        callback_data=f"cat_move_to:0:{telegram_id}",
    ))
    return builder.as_markup()


def category_salary_confirm_keyboard(category_id: int) -> InlineKeyboardMarkup:
    """Подтверждение выдачи зарплаты."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Начислить", callback_data="cat_salary_confirm"),
        InlineKeyboardButton(text="❌ Отмена",     callback_data=f"cat_view:{category_id}"),
    )
    return builder.as_markup()


def category_penalty_scope_keyboard(category_id: int) -> InlineKeyboardMarkup:
    """Выбор — вся категория или один сотрудник."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="👥 Всей категории",
        callback_data=f"cat_penalty_all:{category_id}",
    ))
    builder.row(InlineKeyboardButton(
        text="👤 Одному сотруднику",
        callback_data=f"cat_penalty_one:{category_id}",
    ))
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"cat_view:{category_id}"))
    return builder.as_markup()


def category_penalty_pick_member_keyboard(category_id: int, members: list[dict]) -> InlineKeyboardMarkup:
    """Список сотрудников для персонального штрафа."""
    from bot.utils.ranks import rank_emoji, DEFAULT_RANK
    builder = InlineKeyboardBuilder()
    for m in members:
        r = m.get("rank") or DEFAULT_RANK
        nick = m["nickname"]
        if len(nick) > 15:
            nick = nick[:12] + "..."
        builder.row(InlineKeyboardButton(
            text=f"{rank_emoji(r)} {nick}",
            callback_data=f"cat_penalty_pick:{category_id}:{m['telegram_id']}",
        ))
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"cat_penalty:{category_id}"))
    return builder.as_markup()


def category_penalty_confirm_keyboard(category_id: int) -> InlineKeyboardMarkup:
    """Подтверждение штрафа."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Списать", callback_data="cat_penalty_confirm"),
        InlineKeyboardButton(text="❌ Отмена",   callback_data=f"cat_view:{category_id}"),
    )
    return builder.as_markup()


def category_salary_one_pick_keyboard(category_id: int, members: list[dict]) -> InlineKeyboardMarkup:
    """Список сотрудников для персональной зарплаты."""
    from bot.utils.ranks import rank_emoji, DEFAULT_RANK
    builder = InlineKeyboardBuilder()
    for m in members:
        r = m.get("rank") or DEFAULT_RANK
        nick = m["nickname"]
        if len(nick) > 15:
            nick = nick[:12] + "..."
        builder.row(InlineKeyboardButton(
            text=f"{rank_emoji(r)} {nick}",
            callback_data=f"cat_salary_one_pick:{category_id}:{m['telegram_id']}",
        ))
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"cat_view:{category_id}"))
    return builder.as_markup()


def category_broadcast_confirm_keyboard(category_id: int) -> InlineKeyboardMarkup:
    """Подтверждение рассылки."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📤 Отправить", callback_data="cat_broadcast_confirm"),
        InlineKeyboardButton(text="❌ Отмена",     callback_data=f"cat_view:{category_id}"),
    )
    return builder.as_markup()


def category_history_keyboard(category_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"cat_view:{category_id}"))
    return builder.as_markup()


def category_coefs_keyboard(categories: list[dict]) -> InlineKeyboardMarkup:
    """Меню коэффициентов всех категорий."""
    builder = InlineKeyboardBuilder()
    for c in categories:
        builder.row(InlineKeyboardButton(
            text=f"{c['name']} — ×{c['coefficient']:g}",
            callback_data=f"cat_coef_edit:{c['id']}",
        ))
    builder.row(InlineKeyboardButton(text="⬅️ Управление Staff", callback_data="admin_staff"))
    return builder.as_markup()
