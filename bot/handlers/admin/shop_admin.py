"""
Обработчики администратора: To-Do лист и настройки магазина.
"""

import json
from datetime import datetime

from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext

from bot.config import config
from bot.database import queries
from bot.keyboards.admin import (
    admin_panel_keyboard,
    shop_order_action_keyboard,
    todo_nav_keyboard,
    todo_history_nav_keyboard,
    admin_shop_settings_keyboard,
    admin_shop_toggle_keyboard,
    admin_shop_ticket_price_keyboard,
    admin_shop_roulette_cost_keyboard,
    admin_back_keyboard,
)
from bot.states.forms import AdminShopSettings
from bot.utils.formatters import format_datetime
from bot.utils.logger import log_admin_action

router = Router()
PAGE_SIZE = 5


def _is_owner(callback: CallbackQuery) -> bool:
    return callback.from_user.id == config.owner_id


def _format_order(order: dict) -> str:
    """Форматировать заявку магазина для отображения."""
    try:
        details = json.loads(order["details"])
    except Exception:
        details = {}

    order_type = order["order_type"]
    nickname = order.get("nickname", "—")
    tg_id = order.get("user_telegram_id", "—")
    created = format_datetime(order["created_at"])

    status_map = {
        "pending":   "🟡 Ожидает выполнения",
        "completed": "🟢 Выполнено",
        "ignored":   "🔴 Игнорировано",
    }
    status = status_map.get(order["status"], order["status"])

    if order_type == "roulette":
        item_emoji = details.get("item_emoji", "🎲")
        item_name  = details.get("item_name", "Рулетка")
        ticket_name = details.get("ticket_name", "тикет")
        cost = details.get("cost", 1)
        type_label = f"🎲 Покупка рулетки: {item_emoji} {item_name}"
        detail_line = f"💸 Цена: {cost} {ticket_name}"

    elif order_type == "exchange":
        ticket_name = details.get("ticket_name", "тикет")
        amount = details.get("amount", 0)
        total_cost = details.get("total_cost", 0)
        type_label = f"🔄 Обмен баллов на {ticket_name}"
        detail_line = f"⭐ Списано: {total_cost:g} б. → 🎫 {amount} тикет(ов)"

    elif order_type == "withdraw":
        amount = details.get("amount", 0)
        payout = details.get("payout", 0)
        type_label = "💰 Вывод баллов"
        detail_line = f"⭐ {amount:g} баллов → 💵 {payout:g} рублей"

    else:
        type_label = f"📦 {order_type}"
        detail_line = ""

    lines = [
        f"📋 <b>Заявка #{order['id']}</b>",
        f"👤 Пользователь: <b>{nickname}</b>",
        f"🆔 Telegram ID: <code>{tg_id}</code>",
        f"📦 Тип: {type_label}",
        f"📌 Статус: {status}",
        f"📅 Дата: {created}",
    ]
    if detail_line:
        lines.append(detail_line)

    return "\n".join(lines)


# To-Do лист

@router.callback_query(F.data == "admin_todo")
async def admin_todo_list(callback: CallbackQuery) -> None:
    """Показать To-Do лист (первая заявка)."""
    if not _is_owner(callback):
        await callback.answer("⛔ Доступ запрещён.", show_alert=True)
        return
    await _show_todo_at(callback, 0)


@router.callback_query(F.data.startswith("admin_todo:"))
async def admin_todo_page(callback: CallbackQuery) -> None:
    """Навигация по To-Do списку."""
    if not _is_owner(callback):
        await callback.answer("⛔ Доступ запрещён.", show_alert=True)
        return
    offset = int(callback.data.split(":")[1])
    await _show_todo_at(callback, offset)


async def _show_todo_at(callback: CallbackQuery, offset: int) -> None:
    """Внутренняя функция: показать заявку по индексу."""
    orders = await queries.get_pending_shop_orders()
    total = len(orders)

    if not orders:
        await callback.message.edit_text(
            "📋 <b>To-Do лист</b>\n\n"
            "✅ Нет активных заявок.",
            reply_markup=todo_nav_keyboard(0, 0),
            parse_mode="HTML"
        )
        await callback.answer()
        return

    offset = max(0, min(offset, total - 1))
    order = orders[offset]

    text = (
        f"📋 <b>To-Do лист</b> ({offset + 1}/{total})\n\n"
        + _format_order(order)
    )

    # Клавиатура: кнопки действий + навигация
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Выполнено",    callback_data=f"todo_complete:{order['id']}"),
        InlineKeyboardButton(text="🚫 Игнорировать", callback_data=f"todo_ignore:{order['id']}"),
    )
    # Навигация
    nav_row = []
    if offset > 0:
        nav_row.append(InlineKeyboardButton(text="◀️ Назад", callback_data=f"admin_todo:{offset - 1}"))
    if offset + 1 < total:
        nav_row.append(InlineKeyboardButton(text="▶️ Вперёд", callback_data=f"admin_todo:{offset + 1}"))
    if nav_row:
        builder.row(*nav_row)
    builder.row(
        InlineKeyboardButton(text="📋 История", callback_data="admin_todo_history:0"),
        InlineKeyboardButton(text="👑 Админка", callback_data="admin_panel"),
    )

    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("todo_complete:"))
async def admin_todo_complete(callback: CallbackQuery) -> None:
    """Отметить заявку как выполненную."""
    if not _is_owner(callback):
        await callback.answer("⛔ Доступ запрещён.", show_alert=True)
        return

    order_id = int(callback.data.split(":")[1])
    order = await queries.get_shop_order_by_id(order_id)
    if not order:
        await callback.answer("❌ Заявка не найдена.", show_alert=True)
        return
    if order["status"] != "pending":
        await callback.answer("⚠️ Заявка уже обработана.", show_alert=True)
        return

    await queries.update_shop_order_status(order_id, "completed")
    log_admin_action(callback.from_user.id, "TODO_COMPLETE", f"Заявка #{order_id} выполнена")

    await callback.answer("✅ Заявка отмечена как выполненная!")

    # Показываем следующую заявку
    await _show_todo_at(callback, 0)


@router.callback_query(F.data.startswith("todo_ignore:"))
async def admin_todo_ignore(callback: CallbackQuery) -> None:
    """Игнорировать заявку."""
    if not _is_owner(callback):
        await callback.answer("⛔ Доступ запрещён.", show_alert=True)
        return

    order_id = int(callback.data.split(":")[1])
    order = await queries.get_shop_order_by_id(order_id)
    if not order:
        await callback.answer("❌ Заявка не найдена.", show_alert=True)
        return
    if order["status"] != "pending":
        await callback.answer("⚠️ Заявка уже обработана.", show_alert=True)
        return

    await queries.update_shop_order_status(order_id, "ignored")
    log_admin_action(callback.from_user.id, "TODO_IGNORE", f"Заявка #{order_id} игнорирована")

    await callback.answer("🚫 Заявка игнорирована.")

    # Показываем следующую заявку
    await _show_todo_at(callback, 0)


# История To-Do заявок

@router.callback_query(F.data.startswith("admin_todo_history:"))
async def admin_todo_history(callback: CallbackQuery) -> None:
    """История выполненных/игнорированных заявок магазина."""
    if not _is_owner(callback):
        await callback.answer("⛔ Доступ запрещён.", show_alert=True)
        return

    offset = int(callback.data.split(":")[1])
    orders = await queries.get_shop_orders_history(limit=PAGE_SIZE, offset=offset)
    total = await queries.count_shop_orders_history()

    if not orders:
        await callback.message.edit_text(
            "📋 <b>История заявок магазина</b>\n\nИстория пуста.",
            reply_markup=todo_history_nav_keyboard(offset, total, PAGE_SIZE),
            parse_mode="HTML"
        )
        await callback.answer()
        return

    lines = [f"📋 <b>История заявок магазина</b> (стр. {offset // PAGE_SIZE + 1})\n"]
    for order in orders:
        completed_at = format_datetime(order.get("completed_at") or "")
        lines.append(_format_order(order))
        if completed_at:
            lines.append(f"🏁 Завершено: {completed_at}")
        lines.append("─" * 30)

    text = "\n".join(lines).rstrip("─").rstrip()

    await callback.message.edit_text(
        text,
        reply_markup=todo_history_nav_keyboard(offset, total, PAGE_SIZE),
        parse_mode="HTML"
    )
    await callback.answer()


# Настройки магазина

@router.callback_query(F.data == "admin_shop_settings")
async def admin_shop_settings(callback: CallbackQuery, state: FSMContext) -> None:
    """Главное меню настроек магазина."""
    if not _is_owner(callback):
        await callback.answer("⛔ Доступ запрещён.", show_alert=True)
        return
    await state.clear()

    settings = await queries.get_shop_settings()
    rate = float(settings.get("withdraw_rate", "9"))
    min_w = float(settings.get("withdraw_min", "50"))

    await callback.message.edit_text(
        f"🛒 <b>Настройки магазина</b>\n\n"
        f"💰 Курс вывода: <b>{rate:g} руб/балл</b>\n"
        f"⏩ Минимум вывода: <b>{min_w:g} баллов</b>\n\n"
        f"Выберите параметр для изменения:",
        reply_markup=admin_shop_settings_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


# Курс вывода

@router.callback_query(F.data == "admin_shop_set_rate")
async def admin_shop_set_rate_start(callback: CallbackQuery, state: FSMContext) -> None:
    """Начать ввод нового курса вывода."""
    if not _is_owner(callback):
        await callback.answer("⛔ Доступ запрещён.", show_alert=True)
        return

    settings = await queries.get_shop_settings()
    current = float(settings.get("withdraw_rate", "9"))

    await state.set_state(AdminShopSettings.waiting_withdraw_rate)
    from bot.keyboards.admin import cancel_admin_keyboard
    await callback.message.edit_text(
        f"💰 <b>Изменение курса вывода</b>\n\n"
        f"Текущий курс: <b>{current:g} руб/балл</b>\n\n"
        f"Введите новый курс (рублей за 1 балл):",
        reply_markup=cancel_admin_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(AdminShopSettings.waiting_withdraw_rate)
async def admin_shop_set_rate_input(message: Message, state: FSMContext) -> None:
    """Обработка нового курса вывода."""
    try:
        rate = float(message.text.strip().replace(",", "."))
        if rate <= 0:
            raise ValueError
    except ValueError:
        await message.answer("⚠️ Введите положительное число (например: 9 или 9.5)")
        return

    await queries.update_shop_setting("withdraw_rate", str(rate))
    await state.clear()
    log_admin_action(message.from_user.id, "SHOP_SET_RATE", f"Новый курс: {rate:g} руб/балл")

    await message.answer(
        f"✅ Курс вывода обновлён: <b>{rate:g} руб/балл</b>",
        parse_mode="HTML"
    )


# Минимум вывода

@router.callback_query(F.data == "admin_shop_set_min")
async def admin_shop_set_min_start(callback: CallbackQuery, state: FSMContext) -> None:
    """Начать ввод нового минимума вывода."""
    if not _is_owner(callback):
        await callback.answer("⛔ Доступ запрещён.", show_alert=True)
        return

    settings = await queries.get_shop_settings()
    current = float(settings.get("withdraw_min", "50"))

    await state.set_state(AdminShopSettings.waiting_withdraw_min)
    from bot.keyboards.admin import cancel_admin_keyboard
    await callback.message.edit_text(
        f"⏩ <b>Изменение минимума вывода</b>\n\n"
        f"Текущий минимум: <b>{current:g} баллов</b>\n\n"
        f"Введите новый минимум (баллов):",
        reply_markup=cancel_admin_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(AdminShopSettings.waiting_withdraw_min)
async def admin_shop_set_min_input(message: Message, state: FSMContext) -> None:
    """Обработка нового минимума вывода."""
    try:
        min_val = float(message.text.strip().replace(",", "."))
        if min_val <= 0:
            raise ValueError
    except ValueError:
        await message.answer("⚠️ Введите положительное число (например: 50)")
        return

    await queries.update_shop_setting("withdraw_min", str(min_val))
    await state.clear()
    log_admin_action(message.from_user.id, "SHOP_SET_MIN", f"Новый минимум: {min_val:g} баллов")

    await message.answer(
        f"✅ Минимум вывода обновлён: <b>{min_val:g} баллов</b>",
        parse_mode="HTML"
    )


# Включение/выключение товаров

@router.callback_query(F.data == "admin_shop_toggle_items")
async def admin_shop_toggle_menu(callback: CallbackQuery) -> None:
    """Меню включения/выключения товаров."""
    if not _is_owner(callback):
        await callback.answer("⛔ Доступ запрещён.", show_alert=True)
        return

    settings = await queries.get_shop_settings()
    await callback.message.edit_text(
        "🔧 <b>Управление доступностью товаров</b>\n\n"
        "Нажмите на товар, чтобы включить/выключить:",
        reply_markup=admin_shop_toggle_keyboard(settings),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_shop_toggle:"))
async def admin_shop_toggle_item(callback: CallbackQuery) -> None:
    """Переключить доступность товара."""
    if not _is_owner(callback):
        await callback.answer("⛔ Доступ запрещён.", show_alert=True)
        return

    item_key = callback.data.split(":")[1]
    settings = await queries.get_shop_settings()
    current = settings.get(f"item_{item_key}_active", "1")
    new_val = "0" if current == "1" else "1"
    await queries.update_shop_setting(f"item_{item_key}_active", new_val)

    status = "включён" if new_val == "1" else "выключен"
    log_admin_action(callback.from_user.id, "SHOP_TOGGLE", f"{item_key}: {status}")
    await callback.answer(f"{'✅' if new_val == '1' else '🚫'} Товар {status}!")

    # Обновляем меню
    settings = await queries.get_shop_settings()
    await callback.message.edit_reply_markup(
        reply_markup=admin_shop_toggle_keyboard(settings)
    )


# Цены тикетов (баллы)

@router.callback_query(F.data == "admin_shop_ticket_prices")
async def admin_shop_ticket_prices_menu(callback: CallbackQuery) -> None:
    """Меню цен тикетов."""
    if not _is_owner(callback):
        await callback.answer("⛔ Доступ запрещён.", show_alert=True)
        return

    settings = await queries.get_shop_settings()
    await callback.message.edit_text(
        "🎫 <b>Цены тикетов (баллы за 1 тикет)</b>\n\n"
        "Выберите тикет для изменения цены:",
        reply_markup=admin_shop_ticket_price_keyboard(settings),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_shop_set_tprice:"))
async def admin_shop_set_ticket_price_start(callback: CallbackQuery, state: FSMContext) -> None:
    """Начать ввод новой цены тикета."""
    if not _is_owner(callback):
        await callback.answer("⛔ Доступ запрещён.", show_alert=True)
        return

    ticket_key = callback.data.split(":")[1]
    settings = await queries.get_shop_settings()
    current = float(settings.get(f"ticket_price_{ticket_key}", "0"))

    await state.set_state(AdminShopSettings.waiting_ticket_price)
    await state.update_data(ticket_key=ticket_key)

    from bot.keyboards.admin import cancel_admin_keyboard
    from bot.keyboards.user import TICKET_NAMES_SHORT
    t_emoji, t_name = TICKET_NAMES_SHORT.get(ticket_key, ("🎫", ticket_key))

    await callback.message.edit_text(
        f"🎫 <b>Изменение цены: {t_emoji} {t_name} тикет</b>\n\n"
        f"Текущая цена: <b>{current:g} баллов</b>\n\n"
        f"Введите новую цену (баллов за 1 тикет):",
        reply_markup=cancel_admin_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(AdminShopSettings.waiting_ticket_price)
async def admin_shop_set_ticket_price_input(message: Message, state: FSMContext) -> None:
    """Обработка новой цены тикета."""
    try:
        price = float(message.text.strip().replace(",", "."))
        if price <= 0:
            raise ValueError
    except ValueError:
        await message.answer("⚠️ Введите положительное число (например: 10 или 2.5)")
        return

    data = await state.get_data()
    ticket_key = data.get("ticket_key", "")
    await queries.update_shop_setting(f"ticket_price_{ticket_key}", str(price))
    await state.clear()
    log_admin_action(message.from_user.id, "SHOP_SET_TPRICE", f"{ticket_key}: {price:g} баллов")

    from bot.keyboards.user import TICKET_NAMES_SHORT
    t_emoji, t_name = TICKET_NAMES_SHORT.get(ticket_key, ("🎫", ticket_key))

    await message.answer(
        f"✅ Цена {t_emoji} {t_name} тикета обновлена: <b>{price:g} баллов</b>",
        parse_mode="HTML"
    )


# Стоимость рулеток (тикеты)

@router.callback_query(F.data == "admin_shop_roulette_costs")
async def admin_shop_roulette_costs_menu(callback: CallbackQuery) -> None:
    """Меню стоимости рулеток."""
    if not _is_owner(callback):
        await callback.answer("⛔ Доступ запрещён.", show_alert=True)
        return

    settings = await queries.get_shop_settings()
    await callback.message.edit_text(
        "🛒 <b>Стоимость рулеток (тикеты)</b>\n\n"
        "Выберите рулетку для изменения стоимости:",
        reply_markup=admin_shop_roulette_cost_keyboard(settings),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_shop_set_rcost:"))
async def admin_shop_set_roulette_cost_start(callback: CallbackQuery, state: FSMContext) -> None:
    """Начать ввод новой стоимости рулетки."""
    if not _is_owner(callback):
        await callback.answer("⛔ Доступ запрещён.", show_alert=True)
        return

    roulette_key = callback.data.split(":")[1]
    settings = await queries.get_shop_settings()
    current = int(float(settings.get(f"roulette_cost_{roulette_key}", "1")))

    await state.set_state(AdminShopSettings.waiting_roulette_cost)
    await state.update_data(roulette_key=roulette_key)

    from bot.keyboards.admin import cancel_admin_keyboard
    names = {
        "platinum": "💎 Платиновая",
        "gold":     "🥇 Золотая",
        "silver":   "🥈 Серебряная",
        "bronze":   "🥉 Бронзовая",
        "support":  "🎁 Вспомогательная",
        "help":     "💪 Хелп",
    }
    roulette_name = names.get(roulette_key, roulette_key)

    await callback.message.edit_text(
        f"🛒 <b>Изменение стоимости: {roulette_name} рулетка</b>\n\n"
        f"Текущая стоимость: <b>{current} тикет(ов)</b>\n\n"
        f"Введите новую стоимость (целое число тикетов):",
        reply_markup=cancel_admin_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(AdminShopSettings.waiting_roulette_cost)
async def admin_shop_set_roulette_cost_input(message: Message, state: FSMContext) -> None:
    """Обработка новой стоимости рулетки."""
    try:
        cost = int(message.text.strip())
        if cost <= 0:
            raise ValueError
    except ValueError:
        await message.answer("⚠️ Введите положительное целое число (например: 1 или 2)")
        return

    data = await state.get_data()
    roulette_key = data.get("roulette_key", "")
    await queries.update_shop_setting(f"roulette_cost_{roulette_key}", str(cost))
    await state.clear()
    log_admin_action(message.from_user.id, "SHOP_SET_RCOST", f"{roulette_key}: {cost} тикет(ов)")

    names = {
        "platinum": "💎 Платиновая",
        "gold":     "🥇 Золотая",
        "silver":   "🥈 Серебряная",
        "bronze":   "🥉 Бронзовая",
        "support":  "🎁 Вспомогательная",
        "help":     "💪 Хелп",
    }
    roulette_name = names.get(roulette_key, roulette_key)

    await message.answer(
        f"✅ Стоимость {roulette_name} рулетки обновлена: <b>{cost} тикет(ов)</b>",
        parse_mode="HTML"
    )
