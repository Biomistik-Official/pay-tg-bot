"""
Вспомогательные функции для форматирования сообщений бота.
"""

from datetime import datetime


def format_datetime(dt_str: str) -> str:
    """Форматировать дату из SQLite в читаемый вид."""
    try:
        dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
        return dt.strftime("%d.%m.%Y %H:%M")
    except (ValueError, TypeError):
        return dt_str or "—"


# Словарь названий типов тикетов
TICKET_NAMES = {
    "platinum": ("💎", "Платиновый"),
    "gold":     ("🥇", "Золотой"),
    "silver":   ("🥈", "Серебряный"),
    "bronze":   ("🥉", "Бронзовый"),
    "support":  ("🎁", "Вспомогательный"),
    "help":     ("💪", "Хелп"),
}


def format_operation(operation: str, currency_type: str, amount: float) -> str:
    """Форматировать строку операции для истории."""
    if operation == "add":
        sign = "➕"
    elif operation == "subtract":
        sign = "➖"
    else:
        sign = "🔄"

    if currency_type.startswith("tickets_"):
        key = currency_type.replace("tickets_", "")
        emoji, name = TICKET_NAMES.get(key, ("🎫", "Тикет"))
        amount_str = f"{int(amount)}"
        return f"{sign} {emoji} {amount_str} шт. ({name} тикет)"
    elif currency_type == "unwarns":
        int_amount = int(amount)
        if operation == "add":
            return f"➕ Выдан Анварн" if int_amount == 1 else f"➕ Выдано {int_amount} Анварнов"
        elif operation == "subtract":
            return f"➖ Снят Анварн" if int_amount == 1 else f"➖ Снято {int_amount} Анварнов"
        else:
            return f"✏️ Установлено {int_amount} Анварнов"
    elif currency_type == "unmutes":
        int_amount = int(amount)
        if operation == "add":
            return f"➕ Выдан Анмут" if int_amount == 1 else f"➕ Выдано {int_amount} Анмутов"
        elif operation == "subtract":
            return f"➖ Снят Анмут" if int_amount == 1 else f"➖ Снято {int_amount} Анмутов"
        else:
            return f"✏️ Установлено {int_amount} Анмутов"
    elif currency_type == "rubles":
        amount_str = f"{amount:g}"
        if operation == "add":
            return f"➕ 💰 {amount_str} ₽ (рубли)"
        elif operation == "subtract":
            return f"➖ 💰 {amount_str} ₽ (рубли)"
        else:
            return f"✏️ 💰 Установлено {amount_str} ₽"
    elif currency_type == "stars":
        int_amount = int(amount)
        if operation == "add":
            return f"➕ 🌟 {int_amount} шт. (звёзды)"
        elif operation == "subtract":
            return f"➖ 🌟 {int_amount} шт. (звёзды)"
        else:
            return f"✏️ 🌟 Установлено {int_amount} звёзд"
    else:
        emoji = "⭐"
        label = "балл"
        int_amount = int(amount)
        if int_amount % 10 == 1 and int_amount % 100 != 11:
            label = "балл"
        elif 2 <= int_amount % 10 <= 4 and not (12 <= int_amount % 100 <= 14):
            label = "балла"
        else:
            label = "баллов"
        amount_str = f"{amount:g}"
        return f"{sign} {emoji} {amount_str} {label}"


def format_profile(user: dict) -> str:
    """Форматировать профиль пользователя."""
    blocked = ""
    if user.get("is_blocked") == 1:
        blocked = " 🚫 (заблокирован)"
    elif user.get("is_blocked") == 2:
        blocked = " ❌ (доступ отключен)"
        
    username = f"@{user['username']}" if user.get("username") else "не задан"

    platinum = user.get('tickets_platinum', 0)
    gold = user.get('tickets_gold', 0)
    silver = user.get('tickets_silver', 0)
    bronze = user.get('tickets_bronze', 0)
    support = user.get('tickets_support', 0)
    help_t = user.get('tickets_help', 0)

    # Красивый список тикетов
    tickets_list = []
    if platinum > 0: tickets_list.append(f"  💎 Платиновый: <b>{platinum}</b> шт.")
    if gold > 0:     tickets_list.append(f"  🥇 Золотой: <b>{gold}</b> шт.")
    if silver > 0:   tickets_list.append(f"  🥈 Серебряный: <b>{silver}</b> шт.")
    if bronze > 0:   tickets_list.append(f"  🥉 Бронзовый: <b>{bronze}</b> шт.")
    if support > 0:  tickets_list.append(f"  🎁 Вспомогательный: <b>{support}</b> шт.")
    if help_t > 0:   tickets_list.append(f"  💪 Хелп тикет: <b>{help_t}</b> шт.")
    
    tickets_text = "\n" + "\n".join(tickets_list) if tickets_list else "  <i>нет тикетов</i>"
    points = user['points']
    rubles = user.get('rubles', 0) or 0
    stars = int(user.get('stars', 0) or 0)

    return (
        f"👤 <b>Профиль игрока</b>{blocked}\n\n"
        f"👤 <b>Никнейм в боте:</b> {user['nickname']}\n"
        f"🏷️ <b>Тег игрока Brawl Stars:</b> <code>{user.get('player_tag', '—')}</code>\n"
        f"🏠 <b>Название клуба:</b> {user.get('club_name', '—')}\n\n"
        f"🔗 <b>Username:</b> {username}\n"
        f"🆔 <b>Telegram ID:</b> <code>{user['telegram_id']}</code>\n\n"
        f"🎫 <b>Тикеты:</b>{tickets_text}\n"
        f"⭐ <b>Баллы:</b> {points:g}\n"
        f"💰 <b>Рубли:</b> {rubles:g} ₽\n"
        f"🌟 <b>Звёзды:</b> {stars}\n"
        f"⚠️ <b>Анварны:</b> {user.get('unwarns', 0)}\n"
        f"🔇 <b>Анмуты:</b> {user.get('unmutes', 0)}\n\n"
        f"✅ <b>Одобрено заявок:</b> {user['approved_requests']}\n"
        f"📅 <b>Дата регистрации:</b> {format_datetime(user['registered_at'])}"
    )


def format_transaction(tx: dict) -> str:
    """Форматировать одну транзакцию для истории."""
    op_str = format_operation(tx["operation"], tx["currency_type"], tx["amount"])
    date_str = format_datetime(tx["created_at"])
    performer = tx.get("performer_nickname") or "Система"

    reason = f"\n   📝 {tx['reason']}" if tx.get("reason") else ""
    return (
        f"{op_str}\n"
        f"   📅 {date_str} · 👑 {performer}"
        f"{reason}"
    )


def format_request_for_owner(req: dict, user: dict) -> str:
    """Форматировать заявку для сообщения Owner."""
    # ТГ тег и ИД в скобках
    username = user.get("username")
    user_display = f"@{username}" if username else user.get("nickname", "—")
    user_info = f"{user_display} ({user['telegram_id']})"

    if req["currency_type"].startswith("tickets_"):
        key = req["currency_type"].replace("tickets_", "")
        emoji, name = TICKET_NAMES.get(key, ("🎫", "Тикет"))
        amount_val = int(req.get("amount", 1))
        return (
            f"📨 <b>Новая заявка на тикеты</b>\n\n"
            f"👤 <b>Пользователь:</b> {user_info}\n"
            f"🎫 <b>Тип тикета:</b> {emoji} {name}\n"
            f"🔢 <b>Количество:</b> {amount_val} шт.\n"
            f"📝 <b>Причина:</b> {req['reason']}\n"
            f"🕐 <b>Время:</b> {format_datetime(req['created_at'])}"
        )
    else:
        amount_str = f"{req['amount']:g}"
        return (
            f"📨 <b>Новая заявка на баллы</b>\n\n"
            f"👤 <b>Пользователь:</b> {user_info}\n"
            f"⭐ <b>Количество:</b> {amount_str}\n"
            f"📝 <b>Причина:</b> {req['reason']}\n"
            f"🕐 <b>Время:</b> {format_datetime(req['created_at'])}"
        )


def format_request_history_item(req: dict) -> str:
    """Форматировать заявку в истории."""
    if req["currency_type"].startswith("tickets_"):
        key = req["currency_type"].replace("tickets_", "")
        emoji, name = TICKET_NAMES.get(key, ("🎫", "Тикет"))
        label = f"{emoji} {name} тикет"
    else:
        emoji = "⭐"
        label = f"{req['amount']:g} баллов"

    status_map = {
        "approved": "✅ Одобрена",
        "rejected": "❌ Отклонена",
        "pending": "⏳ Ожидает",
    }
    status = status_map.get(req["status"], req["status"])
    date_str = format_datetime(req["created_at"])
    nickname = req.get("nickname", "—")

    return (
        f"#{req['id']} | {status}\n"
        f"👤 {nickname} · {label}\n"
        f"📝 {req['reason']}\n"
        f"📅 {date_str}"
    )
