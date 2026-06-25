"""
Управление баллами (Admin).
"""

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from bot.config import config
from bot.database import queries
from bot.keyboards.admin import (
    manage_points_keyboard,
    manage_currency_from_profile_keyboard,
    admin_back_keyboard,
    cancel_admin_keyboard,
)
from bot.states.forms import ManagePoints, SetBalance
from bot.utils.logger import log_admin_action

router = Router()


def _is_owner(callback: CallbackQuery) -> bool:
    return callback.from_user.id == config.owner_id


# ──────────────────────────────────────────────
# Главное меню управления баллами
# ──────────────────────────────────────────────

@router.callback_query(F.data == "admin_points")
async def admin_points_menu(callback: CallbackQuery) -> None:
    if not _is_owner(callback):
        await callback.answer("⛔ Доступ запрещён.", show_alert=True)
        return

    await callback.message.edit_text(
        "⭐ <b>Управление баллами</b>\n\nВыберите действие:",
        reply_markup=manage_points_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()
@router.callback_query(F.data.startswith("manage_points:"))
async def manage_points_from_profile(callback: CallbackQuery) -> None:
    if not _is_owner(callback):
        await callback.answer("⛔ Доступ запрещён.", show_alert=True)
        return

    telegram_id = int(callback.data.split(":")[1])
    user = await queries.get_user_by_telegram_id(telegram_id)
    if not user:
        await callback.answer("Пользователь не найден.", show_alert=True)
        return

    points_str = f"{user['points']:g}"
    await callback.message.edit_text(
        f"👤 <b>Управление баллами: {user['nickname']}</b>\n"
        f"⭐ Текущий баланс: <b>{points_str}</b>\n\n"
        f"Выберите действие:",
        reply_markup=manage_currency_from_profile_keyboard(telegram_id, "points"),
        parse_mode="HTML"
    )
    await callback.answer()


# ──────────────────────────────────────────────
# Инициализация операций из профиля пользователя
# ──────────────────────────────────────────────

@router.callback_query(F.data.startswith("give_points_to:"))
async def give_points_to_user(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_owner(callback):
        await callback.answer("⛔ Доступ запрещён.", show_alert=True)
        return

    telegram_id = int(callback.data.split(":")[1])
    await state.set_state(ManagePoints.waiting_amount)
    await state.update_data(operation="add", target_telegram_id=telegram_id)
    await callback.message.edit_text(
        "➕ <b>Выдача баллов</b>\n\nВведите количество баллов для выдачи:",
        reply_markup=cancel_admin_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("take_points_from:"))
async def take_points_from_user(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_owner(callback):
        await callback.answer("⛔ Доступ запрещён.", show_alert=True)
        return

    telegram_id = int(callback.data.split(":")[1])
    await state.set_state(ManagePoints.waiting_amount)
    await state.update_data(operation="subtract", target_telegram_id=telegram_id)
    await callback.message.edit_text(
        "➖ <b>Снятие баллов</b>\n\nВведите количество баллов для снятия:",
        reply_markup=cancel_admin_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("set_points_for:"))
async def set_points_for_user(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_owner(callback):
        await callback.answer("⛔ Доступ запрещён.", show_alert=True)
        return

    telegram_id = int(callback.data.split(":")[1])
    await state.set_state(SetBalance.waiting_amount)
    await state.update_data(currency_type="points", target_telegram_id=telegram_id)
    await callback.message.edit_text(
        "🔄 <b>Установить баланс баллов</b>\n\nВведите новое количество баллов:",
        reply_markup=cancel_admin_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


# ──────────────────────────────────────────────
# Выдать / Снять баллы (с запросом ID)
# ──────────────────────────────────────────────

@router.callback_query(F.data == "give_points")
async def give_points_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_owner(callback):
        await callback.answer("⛔ Доступ запрещён.", show_alert=True)
        return

    await state.set_state(ManagePoints.waiting_user_id)
    await state.update_data(operation="add")
    await callback.message.edit_text(
        "➕ <b>Выдача баллов</b>\n\nВведите Telegram ID пользователя:",
        reply_markup=cancel_admin_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "take_points")
async def take_points_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_owner(callback):
        await callback.answer("⛔ Доступ запрещён.", show_alert=True)
        return

    await state.set_state(ManagePoints.waiting_user_id)
    await state.update_data(operation="subtract")
    await callback.message.edit_text(
        "➖ <b>Снятие баллов</b>\n\nВведите Telegram ID пользователя:",
        reply_markup=cancel_admin_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "set_points")
async def set_points_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_owner(callback):
        await callback.answer("⛔ Доступ запрещён.", show_alert=True)
        return

    await state.set_state(SetBalance.waiting_user_id)
    await state.update_data(currency_type="points")
    await callback.message.edit_text(
        "🔄 <b>Установить баланс баллов</b>\n\nВведите Telegram ID пользователя:",
        reply_markup=cancel_admin_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


# ──────────────────────────────────────────────
# FSM обработчики для баллов
# ──────────────────────────────────────────────

@router.message(ManagePoints.waiting_user_id)
async def points_get_user_id(message: Message, state: FSMContext) -> None:
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
    await state.set_state(ManagePoints.waiting_amount)

    data = await state.get_data()
    op_text = "выдать" if data["operation"] == "add" else "снять"
    await message.answer(
        f"👤 Пользователь: <b>{user['nickname']}</b>\n"
        f"⭐ Текущий баланс: <b>{user['points']}</b>\n\n"
        f"Введите количество баллов ({op_text}):",
        reply_markup=cancel_admin_keyboard(),
        parse_mode="HTML"
    )


@router.message(ManagePoints.waiting_amount)
async def points_get_amount(message: Message, state: FSMContext) -> None:
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
        await message.answer("⚠️ Введите положительное число (например, 5 или 0.5).", reply_markup=cancel_admin_keyboard())
        return

    await state.update_data(amount=amount)
    await state.set_state(ManagePoints.waiting_reason)
    amount_str = f"{amount:g}"
    await message.answer(
        f"⭐ Количество: <b>{amount_str}</b>\n\nВведите причину операции:",
        reply_markup=cancel_admin_keyboard(),
        parse_mode="HTML"
    )


@router.message(ManagePoints.waiting_reason)
async def points_get_reason(message: Message, state: FSMContext, bot: Bot) -> None:
    if not message.text:
        await message.answer("⚠️ Введите причину операции.", reply_markup=cancel_admin_keyboard())
        return

    reason = message.text.strip()
    data = await state.get_data()
    await state.clear()

    telegram_id = data["target_telegram_id"]
    amount = data["amount"]
    operation = data["operation"]

    user = await queries.get_user_by_telegram_id(telegram_id)
    await queries.update_user_balance(user["id"], "points", operation, amount)
    await queries.add_transaction(
        user_id=user["id"],
        currency_type="points",
        operation=operation,
        amount=amount,
        reason=reason,
        performed_by=message.from_user.id
    )

    updated = await queries.get_user_by_telegram_id(telegram_id)
    op_emoji = "➕" if operation == "add" else "➖"
    op_text = "выдано" if operation == "add" else "снято"

    amount_str = f"{amount:g}"
    points_str = f"{updated['points']:g}"

    log_admin_action(
        message.from_user.id,
        f"POINTS_{operation.upper()}",
        f"TG:{telegram_id} ({user['nickname']}): {amount_str} | {reason}"
    )

    await message.answer(
        f"✅ <b>Готово!</b>\n\n"
        f"👤 {user['nickname']}\n"
        f"{op_emoji} ⭐ {op_text}: <b>{amount_str}</b>\n"
        f"📊 Новый баланс: <b>{points_str}</b>\n"
        f"📝 Причина: {reason}",
        reply_markup=admin_back_keyboard(),
        parse_mode="HTML"
    )

    try:
        notif_text = (
            f"{'✅' if operation == 'add' else '➖'} <b>Изменение баланса баллов</b>\n\n"
            f"{op_emoji} ⭐ {op_text.capitalize()}: <b>{amount} баллов</b>\n"
            f"📊 Новый баланс: <b>{updated['points']}</b>\n"
            f"📝 Причина: {reason}"
        )
        await bot.send_message(telegram_id, notif_text, parse_mode="HTML")
    except Exception:
        pass
