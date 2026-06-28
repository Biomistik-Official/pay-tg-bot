"""
Клавиатуры для Owner (Админ-панель).
"""

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def admin_panel_keyboard() -> InlineKeyboardMarkup:
    """Главная панель администратора."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="👥 Пользователи", callback_data="admin_users"),
        InlineKeyboardButton(text="🛠 Управление Staff", callback_data="admin_staff"),
    )
    builder.row(
        InlineKeyboardButton(text="📨 Заявки", callback_data="admin_requests"),
        InlineKeyboardButton(text="📋 To-Do лист", callback_data="admin_todo"),
    )
    builder.row(
        InlineKeyboardButton(text="🛍️ Настройки магазина", callback_data="admin_shop_settings"),
        InlineKeyboardButton(text="📬 Объявления", callback_data="admin_announcements"),
    )
    builder.row(
        InlineKeyboardButton(text="📋 Управление квестами", callback_data="admin_quests"),
        InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats"),
    )
    builder.row(InlineKeyboardButton(text="🎮 Активность клубов", callback_data="ca_menu"))
    builder.row(InlineKeyboardButton(text="⬅️ Главное меню", callback_data="main_menu"))
    return builder.as_markup()

def admin_back_keyboard() -> InlineKeyboardMarkup:
    """Кнопка назад в Админ-панель."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="⬅️ Админ-панель", callback_data="admin_panel"))
    return builder.as_markup()


# ──────────────────────────────────────────────
# Пользователи
# ──────────────────────────────────────────────

def admin_users_keyboard(users: list[dict], offset: int, total: int, page_size: int = 10) -> InlineKeyboardMarkup:
    """Меню управления пользователями с алфавитным списком."""
    builder = InlineKeyboardBuilder()
    
    # Добавляем кнопки для каждого пользователя
    for u in users:
        nick = u["nickname"]
        if len(nick) > 15:
            nick = nick[:12] + "..."
        total_tickets = (
            u.get("tickets_platinum", 0) +
            u.get("tickets_gold", 0) +
            u.get("tickets_silver", 0) +
            u.get("tickets_bronze", 0) +
            u.get("tickets_support", 0) +
            u.get("tickets_help", 0)
        )
        btn_text = f"👤 {nick} ({total_tickets}🎫 | {u['points']}⭐)"
        builder.row(InlineKeyboardButton(text=btn_text, callback_data=f"view_user:{u['telegram_id']}"))
        
    # Кнопки навигации по страницам пользователей
    nav_row = []
    if offset > 0:
        nav_row.append(InlineKeyboardButton(
            text="◀️ Назад",
            callback_data=f"admin_users_page:{max(0, offset - page_size)}"
        ))
    if offset + page_size < total:
        nav_row.append(InlineKeyboardButton(
            text="▶️ Вперёд",
            callback_data=f"admin_users_page:{offset + page_size}"
        ))
    if nav_row:
        builder.row(*nav_row)
        
    # Кнопки поиска
    builder.row(
        InlineKeyboardButton(text="🔍 Поиск по нику", callback_data="search_user_nick"),
        InlineKeyboardButton(text="🔍 Поиск по ID", callback_data="search_user_id")
    )
    
    # Назад в админку
    builder.row(InlineKeyboardButton(text="⬅️ В админ-панель", callback_data="admin_panel"))
    return builder.as_markup()


def user_profile_admin_keyboard(telegram_id: int, is_blocked: bool) -> InlineKeyboardMarkup:
    """Кнопки действий с профилем пользователя."""
    builder = InlineKeyboardBuilder()

    block_text = "🔓 Разблокировать" if is_blocked else "🚫 Заблокировать"
    block_cb = f"unblock_user:{telegram_id}" if is_blocked else f"block_user:{telegram_id}"

    builder.row(InlineKeyboardButton(text="✏️ Изменить никнейм", callback_data=f"change_nick:{telegram_id}"))
    builder.row(InlineKeyboardButton(text="🏷️ Изменить тег Brawl Stars", callback_data=f"change_tag:{telegram_id}"))
    builder.row(InlineKeyboardButton(text=block_text, callback_data=block_cb))
    builder.row(
        InlineKeyboardButton(text="🎫 Тикеты", callback_data=f"manage_tickets:{telegram_id}"),
        InlineKeyboardButton(text="⭐ Баллы", callback_data=f"manage_points:{telegram_id}"),
    )
    builder.row(InlineKeyboardButton(text="⚖️ Модерация", callback_data=f"user_moderation:{telegram_id}"))
    builder.row(InlineKeyboardButton(text="📊 История", callback_data=f"user_history:{telegram_id}:0"))
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_users"))
    return builder.as_markup()


# ──────────────────────────────────────────────
# Управление валютой
# ──────────────────────────────────────────────

def manage_tickets_keyboard() -> InlineKeyboardMarkup:
    """Меню управления тикетами."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="➕ Выдать тикеты", callback_data="give_tickets"))
    builder.row(InlineKeyboardButton(text="➖ Снять тикеты", callback_data="take_tickets"))
    builder.row(InlineKeyboardButton(text="🔄 Изменить баланс", callback_data="set_tickets"))
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_panel"))
    return builder.as_markup()


def manage_points_keyboard() -> InlineKeyboardMarkup:
    """Меню управления баллами."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="➕ Выдать баллы", callback_data="give_points"))
    builder.row(InlineKeyboardButton(text="➖ Снять баллы", callback_data="take_points"))
    builder.row(InlineKeyboardButton(text="🔄 Изменить баланс", callback_data="set_points"))
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_panel"))
    return builder.as_markup()


def manage_currency_from_profile_keyboard(telegram_id: int, currency: str) -> InlineKeyboardMarkup:
    """Управление валютой из профиля пользователя."""
    builder = InlineKeyboardBuilder()
    emoji = "🎫" if currency == "tickets" else "⭐"
    label = "тикеты" if currency == "tickets" else "баллы"

    builder.row(InlineKeyboardButton(
        text=f"➕ Выдать {label}",
        callback_data=f"give_{currency}_to:{telegram_id}"
    ))
    builder.row(InlineKeyboardButton(
        text=f"➖ Снять {label}",
        callback_data=f"take_{currency}_from:{telegram_id}"
    ))
    builder.row(InlineKeyboardButton(
        text=f"🔄 Установить баланс",
        callback_data=f"set_{currency}_for:{telegram_id}"
    ))
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"view_user:{telegram_id}"))
    return builder.as_markup()


def user_moderation_keyboard(telegram_id: int) -> InlineKeyboardMarkup:
    """Меню модерации пользователя (Анварны и Анмуты)."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="➕ Выдать Анварн", callback_data=f"give_unwarn:{telegram_id}"),
        InlineKeyboardButton(text="➖ Снять Анварн", callback_data=f"take_unwarn:{telegram_id}")
    )
    builder.row(
        InlineKeyboardButton(text="✏️ Установить Анварны", callback_data=f"set_unwarn:{telegram_id}")
    )
    builder.row(
        InlineKeyboardButton(text="➕ Выдать Анмут", callback_data=f"give_unmute:{telegram_id}"),
        InlineKeyboardButton(text="➖ Снять Анмут", callback_data=f"take_unmute:{telegram_id}")
    )
    builder.row(
        InlineKeyboardButton(text="✏️ Установить Анмуты", callback_data=f"set_unmute:{telegram_id}")
    )
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"view_user:{telegram_id}"))
    return builder.as_markup()


# ──────────────────────────────────────────────
# Заявки
# ──────────────────────────────────────────────

def admin_requests_keyboard() -> InlineKeyboardMarkup:
    """Меню раздела заявок."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="⏳ Активные заявки", callback_data="pending_requests"))
    builder.row(InlineKeyboardButton(text="📋 История заявок", callback_data="requests_history:0"))
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_panel"))
    return builder.as_markup()


def request_action_keyboard(request_id: int) -> InlineKeyboardMarkup:
    """Кнопки одобрить / отклонить для заявки."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Одобрить", callback_data=f"approve_req:{request_id}"),
        InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_req:{request_id}"),
    )
    return builder.as_markup()


def reject_request_keyboard(request_id: int) -> InlineKeyboardMarkup:
    """Кнопки выбора способа отклонения заявки (без причины / с причиной)."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="⏭️ Без причины", callback_data=f"reject_req_no_reason:{request_id}"))
    builder.row(InlineKeyboardButton(text="📝 Указать причину", callback_data=f"reject_req_with_reason:{request_id}"))
    builder.row(InlineKeyboardButton(text="⬅️ Назад к заявкам", callback_data="pending_requests"))
    return builder.as_markup()


def request_history_nav_keyboard(offset: int, total: int, page_size: int = 5) -> InlineKeyboardMarkup:
    """Навигация по истории заявок."""
    builder = InlineKeyboardBuilder()
    nav_row = []

    if offset > 0:
        nav_row.append(InlineKeyboardButton(
            text="◀️ Назад",
            callback_data=f"requests_history:{max(0, offset - page_size)}"
        ))

    if offset + page_size < total:
        nav_row.append(InlineKeyboardButton(
            text="▶️ Вперёд",
            callback_data=f"requests_history:{offset + page_size}"
        ))

    if nav_row:
        builder.row(*nav_row)

    builder.row(
        InlineKeyboardButton(text="⬅️ Заявки", callback_data="admin_requests"),
        InlineKeyboardButton(text="👑 В админку", callback_data="admin_panel")
    )
    return builder.as_markup()


def user_history_nav_keyboard(telegram_id: int, offset: int, total: int, page_size: int = 5) -> InlineKeyboardMarkup:
    """Навигация по истории операций пользователя (для Owner)."""
    builder = InlineKeyboardBuilder()
    nav_row = []

    if offset > 0:
        nav_row.append(InlineKeyboardButton(
            text="◀️ Назад",
            callback_data=f"user_history:{telegram_id}:{max(0, offset - page_size)}"
        ))

    if offset + page_size < total:
        nav_row.append(InlineKeyboardButton(
            text="▶️ Вперёд",
            callback_data=f"user_history:{telegram_id}:{offset + page_size}"
        ))

    if nav_row:
        builder.row(*nav_row)

    builder.row(InlineKeyboardButton(text="⬅️ К профилю", callback_data=f"view_user:{telegram_id}"))
    return builder.as_markup()


def cancel_admin_keyboard() -> InlineKeyboardMarkup:
    """Отмена действия в админ-панели."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_admin_form"))
    return builder.as_markup()


def ticket_type_admin_keyboard(action: str, telegram_id: int = None) -> InlineKeyboardMarkup:
    """Выбор типа тикета для администратора."""
    builder = InlineKeyboardBuilder()
    tg_id_str = str(telegram_id) if telegram_id else "none"
    from bot.keyboards.user import TICKET_TYPES
    for key, emoji, name, _ in TICKET_TYPES:
        builder.row(InlineKeyboardButton(
            text=f"{emoji} {name}",
            callback_data=f"admin_ticket_type:{action}:{key}:{tg_id_str}"
        ))
    
    # Кнопка отмены
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_admin_form"))
    return builder.as_markup()


# ──────────────────────────────────────────────
# To-Do лист магазина
# ──────────────────────────────────────────────

def shop_order_action_keyboard(order_id: int) -> InlineKeyboardMarkup:
    """Кнопки действий с заявкой магазина."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Выполнено",   callback_data=f"todo_complete:{order_id}"),
        InlineKeyboardButton(text="🚫 Игнорировать", callback_data=f"todo_ignore:{order_id}"),
    )
    return builder.as_markup()


def todo_nav_keyboard(offset: int, total: int, page_size: int = 1) -> InlineKeyboardMarkup:
    """Навигация по To-Do списку."""
    builder = InlineKeyboardBuilder()
    nav_row = []
    if offset > 0:
        nav_row.append(InlineKeyboardButton(
            text="◀️ Назад",
            callback_data=f"admin_todo:{max(0, offset - 1)}"
        ))
    if offset + 1 < total:
        nav_row.append(InlineKeyboardButton(
            text="▶️ Вперёд",
            callback_data=f"admin_todo:{offset + 1}"
        ))
    if nav_row:
        builder.row(*nav_row)
    builder.row(
        InlineKeyboardButton(text="📋 История", callback_data="admin_todo_history:0"),
        InlineKeyboardButton(text="👑 Админка", callback_data="admin_panel"),
    )
    return builder.as_markup()


def todo_history_nav_keyboard(offset: int, total: int, page_size: int = 5) -> InlineKeyboardMarkup:
    """Навигация по истории To-Do."""
    builder = InlineKeyboardBuilder()
    nav_row = []
    if offset > 0:
        nav_row.append(InlineKeyboardButton(
            text="◀️ Назад",
            callback_data=f"admin_todo_history:{max(0, offset - page_size)}"
        ))
    if offset + page_size < total:
        nav_row.append(InlineKeyboardButton(
            text="▶️ Вперёд",
            callback_data=f"admin_todo_history:{offset + page_size}"
        ))
    if nav_row:
        builder.row(*nav_row)
    builder.row(
        InlineKeyboardButton(text="⬅️ To-Do", callback_data="admin_todo:0"),
        InlineKeyboardButton(text="👑 Админка", callback_data="admin_panel"),
    )
    return builder.as_markup()


# ──────────────────────────────────────────────
# Настройки магазина (Admin)
# ──────────────────────────────────────────────

def admin_shop_settings_keyboard() -> InlineKeyboardMarkup:
    """Основное меню настроек магазина."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="💰 Курс вывода (руб/балл)",  callback_data="admin_shop_set_rate"))
    builder.row(InlineKeyboardButton(text="⏩ Минимум вывода (баллов)", callback_data="admin_shop_set_min"))
    builder.row(InlineKeyboardButton(text="🎫 Цены тикетов (баллы)",   callback_data="admin_shop_ticket_prices"))
    builder.row(InlineKeyboardButton(text="🛒 Стоимость рулеток",       callback_data="admin_shop_roulette_costs"))
    builder.row(InlineKeyboardButton(text="🔧 Товары (вкл/выкл)",          callback_data="admin_shop_toggle_items"))
    builder.row(InlineKeyboardButton(text="⬅️ Админ-панель", callback_data="admin_panel"))
    return builder.as_markup()


def admin_shop_toggle_keyboard(settings: dict) -> InlineKeyboardMarkup:
    """Включение/выключение товаров."""
    builder = InlineKeyboardBuilder()
    items = [
        ("platinum", "💎", "Платиновая рулетка"),
        ("gold",     "🥇", "Золотая рулетка"),
        ("silver",   "🥈", "Серебряная рулетка"),
        ("bronze",   "🥉", "Бронзовая рулетка"),
        ("support",  "🎁", "Вспомогательная рулетка"),
        ("help",     "💪", "Хелп рулетка"),
    ]
    for key, emoji, name in items:
        active = settings.get(f"item_{key}_active", "1") == "1"
        status = "✅" if active else "🚫"
        builder.row(InlineKeyboardButton(
            text=f"{status} {emoji} {name}",
            callback_data=f"admin_shop_toggle:{key}"
        ))
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_shop_settings"))
    return builder.as_markup()


def admin_shop_ticket_price_keyboard(settings: dict) -> InlineKeyboardMarkup:
    """Изменение цены тикетов в баллах."""
    builder = InlineKeyboardBuilder()
    items = [
        ("platinum", "💎", "Платиновый"),
        ("gold",     "🥇", "Золотой"),
        ("silver",   "🥈", "Серебряный"),
        ("bronze",   "🥉", "Бронзовый"),
        ("support",  "🎁", "Вспомогательный"),
    ]
    for key, emoji, name in items:
        price = float(settings.get(f"ticket_price_{key}", "0"))
        builder.row(InlineKeyboardButton(
            text=f"{emoji} {name} — {price:g} б.",
            callback_data=f"admin_shop_set_tprice:{key}"
        ))
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_shop_settings"))
    return builder.as_markup()


def admin_shop_roulette_cost_keyboard(settings: dict) -> InlineKeyboardMarkup:
    """Изменение стоимости рулеток."""
    builder = InlineKeyboardBuilder()
    items = [
        ("platinum", "💎", "Платиновая"),
        ("gold",     "🥇", "Золотая"),
        ("silver",   "🥈", "Серебряная"),
        ("bronze",   "🥉", "Бронзовая"),
        ("support",  "🎁", "Вспомогательная"),
        ("help",     "💪", "Хелп"),
    ]
    for key, emoji, name in items:
        cost = int(float(settings.get(f"roulette_cost_{key}", "1")))
        builder.row(InlineKeyboardButton(
            text=f"{emoji} {name} рулетка — {cost} тикет",
            callback_data=f"admin_shop_set_rcost:{key}"
        ))
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_shop_settings"))
    return builder.as_markup()


# ────────────────────────────────────────────
# Управление Staff
# ────────────────────────────────────────────

def admin_staff_keyboard() -> InlineKeyboardMarkup:
    """Меню управления Staff."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="➕ Добавить Staff", callback_data="staff_add"))
    builder.row(InlineKeyboardButton(text="📜 Список Staff", callback_data="staff_list"))
    builder.row(InlineKeyboardButton(text="⬅️ Админ-панель", callback_data="admin_panel"))
    return builder.as_markup()


def staff_list_keyboard(staff_list: list[dict]) -> InlineKeyboardMarkup:
    """Список Staff с возможностью просмотра каждого."""
    builder = InlineKeyboardBuilder()
    for member in staff_list:
        nick = member["nickname"]
        if len(nick) > 15:
            nick = nick[:12] + "..."
        builder.row(InlineKeyboardButton(
            text=f"🛠 {nick}",
            callback_data=f"staff_view:{member['telegram_id']}"
        ))
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_staff"))
    return builder.as_markup()


def staff_member_keyboard(telegram_id: int) -> InlineKeyboardMarkup:
    """Действия с конкретным Staff."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📊 Статистика", callback_data=f"staff_stats:{telegram_id}"))
    builder.row(InlineKeyboardButton(text="❌ Снять роль Staff", callback_data=f"staff_remove:{telegram_id}"))
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="staff_list"))
    return builder.as_markup()


def staff_remove_confirm_keyboard(telegram_id: int) -> InlineKeyboardMarkup:
    """Подтверждение снятия роли Staff."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Да, снять", callback_data=f"staff_remove_confirm:{telegram_id}"),
        InlineKeyboardButton(text="❌ Отмена", callback_data=f"staff_view:{telegram_id}"),
    )
    return builder.as_markup()


# ────────────────────────────────────────────
# Квесты (Admin)
# ────────────────────────────────────────────

def admin_quests_keyboard() -> InlineKeyboardMarkup:
    """Меню управления квестами."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="➕ Создать квест", callback_data="quest_create"))
    builder.row(InlineKeyboardButton(text="📋 Список квестов", callback_data="quest_list"))
    builder.row(InlineKeyboardButton(text="⏳ На проверке", callback_data="quest_submissions"))
    builder.row(InlineKeyboardButton(text="⬅️ Админ-панель", callback_data="admin_panel"))
    return builder.as_markup()


def quest_list_admin_keyboard(quests: list[dict]) -> InlineKeyboardMarkup:
    """Список квестов для Owner."""
    builder = InlineKeyboardBuilder()
    for q in quests:
        status_icon = "🟢" if q["status"] == "active" else "🔴"
        title = q["title"][:20] + "..." if len(q["title"]) > 20 else q["title"]
        builder.row(InlineKeyboardButton(
            text=f"{status_icon} {title}",
            callback_data=f"quest_detail:{q['id']}"
        ))
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_quests"))
    return builder.as_markup()


def quest_detail_admin_keyboard(quest_id: int, is_active: bool) -> InlineKeyboardMarkup:
    """Детали квеста + действия Owner."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"quest_edit:{quest_id}"))
    if is_active:
        builder.row(InlineKeyboardButton(text="🔒 Закрыть квест", callback_data=f"quest_close:{quest_id}"))
    builder.row(InlineKeyboardButton(text="📊 Статистика", callback_data=f"quest_stats:{quest_id}"))
    builder.row(InlineKeyboardButton(text="🗑️ Удалить", callback_data=f"quest_delete:{quest_id}"))
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="quest_list"))
    return builder.as_markup()


def quest_edit_field_keyboard(quest_id: int) -> InlineKeyboardMarkup:
    """Выбор поля для редактирования квеста."""
    builder = InlineKeyboardBuilder()
    fields = [
        ("title",          "📝 Название"),
        ("description",    "📄 Описание"),
        ("reward_amount",  "🎁 Награда"),
        ("max_executors",  "👥 Максимум исполнителей"),
        ("deadline",       "📅 Срок"),
    ]
    for key, label in fields:
        builder.row(InlineKeyboardButton(
            text=label,
            callback_data=f"quest_edit_field:{quest_id}:{key}"
        ))
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"quest_detail:{quest_id}"))
    return builder.as_markup()


def quest_delete_confirm_keyboard(quest_id: int) -> InlineKeyboardMarkup:
    """Подтверждение удаления квеста."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"quest_delete_confirm:{quest_id}"),
        InlineKeyboardButton(text="❌ Отмена", callback_data=f"quest_detail:{quest_id}"),
    )
    return builder.as_markup()


def quest_submission_review_keyboard(assignment_id: int) -> InlineKeyboardMarkup:
    """Кнопки проверки отправленного квеста."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Одобрить", callback_data=f"quest_approve:{assignment_id}"),
        InlineKeyboardButton(text="❌ Отклонить", callback_data=f"quest_reject:{assignment_id}"),
    )
    builder.row(InlineKeyboardButton(text="⬅️ К списку", callback_data="quest_submissions"))
    return builder.as_markup()


def submissions_nav_keyboard(offset: int, total: int) -> InlineKeyboardMarkup:
    """Навигация по заявкам на проверку."""
    builder = InlineKeyboardBuilder()
    nav = []
    if offset > 0:
        nav.append(InlineKeyboardButton(text="◀️ Назад", callback_data=f"quest_submissions:{offset - 1}"))
    if offset + 1 < total:
        nav.append(InlineKeyboardButton(text="▶️ Вперёд", callback_data=f"quest_submissions:{offset + 1}"))
    if nav:
        builder.row(*nav)
    builder.row(InlineKeyboardButton(text="⬅️ В квесты", callback_data="admin_quests"))
    return builder.as_markup()


# ────────────────────────────────────────────
# Объявления (Admin)
# ────────────────────────────────────────────

def announcement_type_keyboard() -> InlineKeyboardMarkup:
    """Выбор типа объявления."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🌐 Глобальное (всем)", callback_data="announce_type:global"))
    builder.row(InlineKeyboardButton(text="🛠 Только Staff", callback_data="announce_type:staff"))
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_panel"))
    return builder.as_markup()


def confirm_announcement_keyboard(ann_type: str) -> InlineKeyboardMarkup:
    """Подтверждение отправки объявления."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📤 Отправить", callback_data=f"announce_confirm:{ann_type}"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="admin_announcements"),
    )
    return builder.as_markup()
