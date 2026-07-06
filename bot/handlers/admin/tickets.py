"""
Управление тикетами (Admin).
"""

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from bot.config import config
from bot.database import queries
from bot.keyboards.admin import (
    manage_tickets_keyboard,
    manage_currency_from_profile_keyboard,
    admin_back_keyboard,
    cancel_admin_keyboard,
    ticket_type_admin_keyboard,
)
from bot.states.forms import ManageTickets, SetBalance
from bot.utils.logger import log_admin_action
from bot.utils.formatters import TICKET_NAMES

router = Router()


def _is_owner(callback: CallbackQuery) -> bool:
    return callback.from_user.id == config.owner_id


# Главное меню управления тикетами

@router.callback_query(F.data == "admin_tickets")
async def admin_tickets_menu(callback: CallbackQuery) -> None:
    if not _is_owner(callback):
        await callback.answer("⛔ Доступ запрещён.", show_alert=True)
        return

    await callback.message.edit_text(
        "🎫 <b>Управление тикетами</b>\n\nВыберите действие:",
        reply_markup=manage_tickets_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("manage_tickets:"))
async def manage_tickets_from_profile(callback: CallbackQuery) -> None:
    if not _is_owner(callback):
        await callback.answer("⛔ Доступ запрещён.", show_alert=True)
        return

    telegram_id = int(callback.data.split(":")[1])
    user = await queries.get_user_by_telegram_id(telegram_id)
    if not user:
        await callback.answer("Пользователь не найден.", show_alert=True)
        return

    total_tickets = (
        user.get("tickets_platinum", 0) +
        user.get("tickets_gold", 0) +
        user.get("tickets_silver", 0) +
        user.get("tickets_bronze", 0) +
        user.get("tickets_support", 0) +
        user.get("tickets_help", 0)
    )
    tickets_str = f"{total_tickets}"
    
    details = (
        f"  💎 Платиновый: <b>{user.get('tickets_platinum', 0)}</b> шт.\n"
        f"  🥇 Золотой: <b>{user.get('tickets_gold', 0)}</b> шт.\n"
        f"  🥈 Серебряный: <b>{user.get('tickets_silver', 0)}</b> шт.\n"
        f"  🥉 Бронзовый: <b>{user.get('tickets_bronze', 0)}</b> шт.\n"
        f"  🎁 Вспомогательный: <b>{user.get('tickets_support', 0)}</b> шт.\n"
        f"  💪 Хелп тикет: <b>{user.get('tickets_help', 0)}</b> шт."
    )

    await callback.message.edit_text(
        f"👤 <b>Управление тикетами: {user['nickname']}</b>\n\n"
        f"🎫 Всего тикетов: <b>{tickets_str}</b> шт.\n"
        f"{details}\n\n"
        f"Выберите действие:",
        reply_markup=manage_currency_from_profile_keyboard(telegram_id, "tickets"),
        parse_mode="HTML"
    )
    await callback.answer()


# Выдача тикетов

@router.callback_query(F.data == "give_tickets")
async def give_tickets_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_owner(callback):
        await callback.answer("⛔ Доступ запрещён.", show_alert=True)
        return

    await state.set_state(ManageTickets.waiting_user_id)
    await state.update_data(operation="add")
    await callback.message.edit_text(
        "➕ <b>Выдача тикетов</b>\n\nВведите Telegram ID пользователя:",
        reply_markup=cancel_admin_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("give_tickets_to:"))
async def give_tickets_to_user(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_owner(callback):
        await callback.answer("⛔ Доступ запрещён.", show_alert=True)
        return

    telegram_id = int(callback.data.split(":")[1])
    await state.set_state(ManageTickets.waiting_ticket_type)
    await state.update_data(operation="add", target_telegram_id=telegram_id)
    await callback.message.edit_text(
        "➕ <b>Выдача тикетов</b>\n\nВыберите тип тикета:",
        reply_markup=ticket_type_admin_keyboard("give", telegram_id),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "take_tickets")
async def take_tickets_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_owner(callback):
        await callback.answer("⛔ Доступ запрещён.", show_alert=True)
        return

    await state.set_state(ManageTickets.waiting_user_id)
    await state.update_data(operation="subtract")
    await callback.message.edit_text(
        "➖ <b>Снятие тикетов</b>\n\nВведите Telegram ID пользователя:",
        reply_markup=cancel_admin_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("take_tickets_from:"))
async def take_tickets_from_user(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_owner(callback):
        await callback.answer("⛔ Доступ запрещён.", show_alert=True)
        return

    telegram_id = int(callback.data.split(":")[1])
    await state.set_state(ManageTickets.waiting_ticket_type)
    await state.update_data(operation="subtract", target_telegram_id=telegram_id)
    await callback.message.edit_text(
        "➖ <b>Снятие тикетов</b>\n\nВыберите тип тикета:",
        reply_markup=ticket_type_admin_keyboard("take", telegram_id),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "set_tickets")
async def set_tickets_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_owner(callback):
        await callback.answer("⛔ Доступ запрещён.", show_alert=True)
        return

    await state.set_state(SetBalance.waiting_user_id)
    await state.update_data(currency_type="tickets")
    await callback.message.edit_text(
        "🔄 <b>Установить баланс тикетов</b>\n\nВведите Telegram ID пользователя:",
        reply_markup=cancel_admin_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("set_tickets_for:"))
async def set_tickets_for_user(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_owner(callback):
        await callback.answer("⛔ Доступ запрещён.", show_alert=True)
        return

    telegram_id = int(callback.data.split(":")[1])
    await state.set_state(SetBalance.waiting_ticket_type)
    await state.update_data(currency_type="tickets", target_telegram_id=telegram_id)
    await callback.message.edit_text(
        "🔄 <b>Установить баланс тикетов</b>\n\nВыберите тип тикета:",
        reply_markup=ticket_type_admin_keyboard("set", telegram_id),
        parse_mode="HTML"
    )
    await callback.answer()


# Выбор типа тикета (Callback)

@router.callback_query(F.data.startswith("admin_ticket_type:"))
async def admin_ticket_type_chosen(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_owner(callback):
        await callback.answer("⛔ Доступ запрещён.", show_alert=True)
        return

    parts = callback.data.split(":")
    action = parts[1]      # "give", "take", "set"
    ticket_key = parts[2]  # "platinum", "gold", etc.
    tg_id_str = parts[3]   # "none" or telegram_id
    
    telegram_id = int(tg_id_str) if tg_id_str != "none" else None
    currency_type = f"tickets_{ticket_key}"
    await state.update_data(currency_type=currency_type)
    
    emoji, name = TICKET_NAMES.get(ticket_key, ("🎫", "Тикет"))

    if action in ("give", "take"):
        await state.set_state(ManageTickets.waiting_amount)
        op_text = "выдачи" if action == "give" else "снятия"
        await callback.message.edit_text(
            f"🎫 Выбран тип: {emoji} <b>{name}</b>\n\n"
            f"Введите количество тикетов для {op_text}:",
            reply_markup=cancel_admin_keyboard(),
            parse_mode="HTML"
        )
    elif action == "set":
        await state.set_state(SetBalance.waiting_amount)
        await callback.message.edit_text(
            f"🎫 Выбран тип: {emoji} <b>{name}</b>\n\n"
            f"Введите новое количество тикетов:",
            reply_markup=cancel_admin_keyboard(),
            parse_mode="HTML"
        )
    await callback.answer()


# Обработчики FSM для тикетов

@router.message(ManageTickets.waiting_user_id)
async def tickets_get_user_id(message: Message, state: FSMContext) -> None:
    try:
        telegram_id = int(message.text.strip())
    except ValueError:
        await message.answer("⚠️ Введите корректный Telegram ID (число).", reply_markup=cancel_admin_keyboard())
        return

    user = await queries.get_user_by_telegram_id(telegram_id)
    if not user:
        await message.answer("❌ Пользователь не найден.", reply_markup=cancel_admin_keyboard())
        return

    data = await state.get_data()
    operation = data["operation"]
    action = "give" if operation == "add" else "take"

    await state.update_data(target_telegram_id=telegram_id)
    await state.set_state(ManageTickets.waiting_ticket_type)

    await message.answer(
        f"👤 Пользователь: <b>{user['nickname']}</b>\n\n"
        f"Выберите тип тикета для операции:",
        reply_markup=ticket_type_admin_keyboard(action, telegram_id),
        parse_mode="HTML"
    )


@router.message(ManageTickets.waiting_amount)
async def tickets_get_amount(message: Message, state: FSMContext) -> None:
    if not message.text:
        await message.answer("⚠️ Введите количество числом.", reply_markup=cancel_admin_keyboard())
        return

    try:
        amount = float(message.text.strip().replace(",", "."))
        if amount <= 0:
            raise ValueError
        if amount.is_integer():
            amount = int(amount)
    except ValueError:
        await message.answer("⚠️ Введите положительное число (например, 5).", reply_markup=cancel_admin_keyboard())
        return

    await state.update_data(amount=amount)
    await state.set_state(ManageTickets.waiting_reason)
    amount_str = f"{amount:g}"
    
    data = await state.get_data()
    currency_type = data["currency_type"]
    ticket_key = currency_type.replace("tickets_", "")
    emoji, name = TICKET_NAMES.get(ticket_key, ("🎫", "Тикет"))

    await message.answer(
        f"🎫 Выбрано: {emoji} {name}\n"
        f"🔢 Количество: <b>{amount_str}</b>\n\n"
        f"Введите причину операции:",
        reply_markup=cancel_admin_keyboard(),
        parse_mode="HTML"
    )


@router.message(ManageTickets.waiting_reason)
async def tickets_get_reason(message: Message, state: FSMContext, bot: Bot) -> None:
    if not message.text:
        await message.answer("⚠️ Введите причину операции.", reply_markup=cancel_admin_keyboard())
        return

    reason = message.text.strip()
    data = await state.get_data()
    await state.clear()

    telegram_id = data["target_telegram_id"]
    amount = data["amount"]
    operation = data["operation"]
    currency_type = data["currency_type"]

    user = await queries.get_user_by_telegram_id(telegram_id)
    await queries.update_user_balance(user["id"], currency_type, operation, amount)
    await queries.add_transaction(
        user_id=user["id"],
        currency_type=currency_type,
        operation=operation,
        amount=amount,
        reason=reason,
        performed_by=message.from_user.id
    )

    updated = await queries.get_user_by_telegram_id(telegram_id)
    op_emoji = "➕" if operation == "add" else "➖"
    op_text = "выдано" if operation == "add" else "снято"

    ticket_key = currency_type.replace("tickets_", "")
    emoji, name = TICKET_NAMES.get(ticket_key, ("🎫", "Тикет"))
    
    amount_str = f"{amount:g}"
    balance_str = f"{updated[currency_type]:g}"

    log_admin_action(
        message.from_user.id,
        f"{currency_type.upper()}_{operation.upper()}",
        f"TG:{telegram_id} ({user['nickname']}): {amount_str} | {reason}"
    )

    await message.answer(
        f"✅ <b>Готово!</b>\n\n"
        f"👤 {user['nickname']}\n"
        f"{op_emoji} {emoji} {name} тикетов {op_text}: <b>{amount_str}</b>\n"
        f"📊 Новый баланс: <b>{balance_str}</b> шт.\n"
        f"📝 Причина: {reason}",
        reply_markup=admin_back_keyboard(),
        parse_mode="HTML"
    )

    # Уведомление пользователю
    try:
        notif_text = (
            f"{'✅' if operation == 'add' else '➖'} <b>Изменение баланса тикетов</b>\n\n"
            f"{op_emoji} {emoji} {name} тикетов {op_text}: <b>{amount_str}</b> шт.\n"
            f"📊 Новый баланс: <b>{balance_str}</b> шт.\n"
            f"📝 Причина: {reason}"
        )
        await bot.send_message(telegram_id, notif_text, parse_mode="HTML")
    except Exception:
        pass


# Установить баланс (SetBalance FSM)

@router.message(SetBalance.waiting_user_id)
async def set_balance_get_user_id(message: Message, state: FSMContext) -> None:
    try:
        telegram_id = int(message.text.strip())
    except ValueError:
        await message.answer("⚠️ Введите корректный Telegram ID (число).", reply_markup=cancel_admin_keyboard())
        return

    user = await queries.get_user_by_telegram_id(telegram_id)
    if not user:
        await message.answer("❌ Пользователь не найден.", reply_markup=cancel_admin_keyboard())
        return

    await state.update_data(target_telegram_id=telegram_id)
    
    data = await state.get_data()
    currency = data.get("currency_type", "tickets")
    
    if currency == "tickets":
        await state.set_state(SetBalance.waiting_ticket_type)
        await message.answer(
            f"👤 Пользователь: <b>{user['nickname']}</b>\n\n"
            f"Выберите тип тикета для изменения баланса:",
            reply_markup=ticket_type_admin_keyboard("set", telegram_id),
            parse_mode="HTML"
        )
    else:
        # Это для баллов
        await state.set_state(SetBalance.waiting_amount)
        await message.answer(
            f"👤 Пользователь: <b>{user['nickname']}</b>\n"
            f"⭐ Текущий баланс: <b>{user['points']}</b>\n\n"
            f"Введите новое значение баланса:",
            reply_markup=cancel_admin_keyboard(),
            parse_mode="HTML"
        )


@router.message(SetBalance.waiting_amount)
async def set_balance_get_amount(message: Message, state: FSMContext, bot: Bot) -> None:
    if not message.text:
        await message.answer("⚠️ Введите количество числом.", reply_markup=cancel_admin_keyboard())
        return

    data = await state.get_data()
    currency = data.get("currency_type", "tickets")

    try:
        amount = float(message.text.strip().replace(",", "."))
        if currency != "points" and amount < 0:
            raise ValueError
        if amount.is_integer():
            amount = int(amount)
    except ValueError:
        if currency != "points":
            await message.answer("⚠️ Введите неотрицательное число.", reply_markup=cancel_admin_keyboard())
        else:
            await message.answer("⚠️ Введите корректное число.", reply_markup=cancel_admin_keyboard())
        return

    await state.clear()

    telegram_id = data["target_telegram_id"]

    user = await queries.get_user_by_telegram_id(telegram_id)
    await queries.update_user_balance(user["id"], currency, "set", amount)
    await queries.add_transaction(
        user_id=user["id"],
        currency_type=currency,
        operation="set",
        amount=amount,
        reason="Установка баланса владельцем",
        performed_by=message.from_user.id
    )

    if currency.startswith("tickets_"):
        ticket_key = currency.replace("tickets_", "")
        emoji, name = TICKET_NAMES.get(ticket_key, ("🎫", "Тикет"))
        label = f"{name} тикетов"
        amount_str = f"{int(amount)}"
    else:
        emoji = "⭐"
        label = "баллов"
        amount_str = f"{amount:g}"
        
    log_admin_action(message.from_user.id, f"SET_{currency.upper()}", f"TG:{telegram_id} → {amount_str}")

    await message.answer(
        f"✅ <b>Баланс установлен!</b>\n\n"
        f"👤 {user['nickname']}\n"
        f"{emoji} {label.capitalize()}: <b>{amount_str}</b>",
        reply_markup=admin_back_keyboard(),
        parse_mode="HTML"
    )

    try:
        await bot.send_message(
            telegram_id,
            f"🔄 <b>Баланс изменён владельцем</b>\n\n"
            f"{emoji} Новый баланс: <b>{amount_str} {label}</b>",
            parse_mode="HTML"
        )
    except Exception:
        pass
