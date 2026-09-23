"""Упрощённое управление ролью Staff."""

import html

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.config import config
from bot.database import queries
from bot.keyboards.admin import (
    admin_staff_keyboard,
    cancel_admin_keyboard,
    staff_list_keyboard,
    staff_member_keyboard,
    staff_remove_confirm_keyboard,
)
from bot.states.forms import ManageStaff
from bot.utils.formatters import format_datetime
from bot.utils.logger import log_admin_action

router = Router()


def _is_owner(telegram_id: int) -> bool:
    return telegram_id == config.owner_id


@router.callback_query(F.data == "admin_staff")
async def show_staff_menu(callback: CallbackQuery) -> None:
    if not _is_owner(callback.from_user.id):
        return await callback.answer("Нет доступа.", show_alert=True)
    await callback.message.edit_text(
        "🛠 <b>Управление Staff</b>",
        reply_markup=admin_staff_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "staff_list")
async def show_staff_list(callback: CallbackQuery) -> None:
    if not _is_owner(callback.from_user.id):
        return await callback.answer("Нет доступа.", show_alert=True)
    staff = await queries.get_all_staff()
    text = f"🛠 <b>Staff</b> ({len(staff)} чел.)" if staff else "🛠 <b>Staff</b>\n\nСписок пуст."
    await callback.message.edit_text(text, reply_markup=staff_list_keyboard(staff))
    await callback.answer()


@router.callback_query(F.data.startswith("staff_view:"))
async def view_staff_member(callback: CallbackQuery) -> None:
    if not _is_owner(callback.from_user.id):
        return await callback.answer("Нет доступа.", show_alert=True)
    telegram_id = int(callback.data.split(":")[1])
    user = await queries.get_user_by_telegram_id(telegram_id)
    if not user or not await queries.get_staff_by_user_id(user["id"]):
        return await callback.answer("Staff не найден.", show_alert=True)

    activity = await queries.get_staff_activity(user["id"])
    treasury = await queries.get_user_treasury(user["id"])
    treasury_name = f"{treasury['emoji']} {treasury['name']}" if treasury else "Не назначена"
    last_activity = format_datetime(activity["last_activity_at"]) if activity["last_activity_at"] else "—"
    text = (
        f"🛠 <b>Staff: {html.escape(user['nickname'])}</b>\n"
        f"@{html.escape(user.get('username') or '—')} · <code>{telegram_id}</code>\n\n"
        f"🏦 Казна: <b>{treasury_name}</b>\n"
        f"⭐ Баллы: <b>{user['points']:g}</b>\n\n"
        f"📊 <b>Активности Staff</b>\n"
        f"Показатель активности: <b>{activity['activity_count']}</b>\n"
        f"Заработано баллов: <b>{activity['earned_points']:g}</b>\n"
        f"Заработано тикетов: <b>{activity['earned_tickets']:g}</b>\n"
        f"Последняя активность: <b>{last_activity}</b>"
    )
    await callback.message.edit_text(text, reply_markup=staff_member_keyboard(telegram_id))
    await callback.answer()


@router.callback_query(F.data == "staff_add")
async def start_add_staff(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_owner(callback.from_user.id):
        return await callback.answer("Нет доступа.", show_alert=True)
    await state.set_state(ManageStaff.waiting_user_search)
    await callback.message.edit_text(
        "🛠 <b>Добавить Staff</b>\n\nВведи никнейм или Telegram ID:",
        reply_markup=cancel_admin_keyboard(),
    )
    await callback.answer()


@router.message(ManageStaff.waiting_user_search)
async def process_add_staff(message: Message, state: FSMContext, bot) -> None:
    if not _is_owner(message.from_user.id):
        return
    query = (message.text or "").strip()
    user = await queries.get_user_by_telegram_id(int(query)) if query.lstrip("-").isdigit() else None
    if not user:
        user = await queries.get_user_by_nickname(query)
    if not user:
        return await message.answer("❌ Пользователь не найден. Попробуй ещё раз:")
    if user["telegram_id"] == config.owner_id:
        return await message.answer("⚠️ Owner нельзя добавить в Staff.")

    await queries.add_staff(user["id"], config.owner_id)
    await state.clear()
    log_admin_action(config.owner_id, "Добавление Staff", f"{user['nickname']} ({user['telegram_id']})")
    try:
        await bot.send_message(user["telegram_id"], "🛠 Тебе выдана роль <b>Staff</b>.")
    except Exception:
        pass
    await message.answer(
        f"✅ <b>{html.escape(user['nickname'])}</b> добавлен в Staff.",
        reply_markup=admin_staff_keyboard(),
    )


@router.callback_query(F.data.startswith("staff_remove:"))
async def confirm_remove_staff(callback: CallbackQuery) -> None:
    if not _is_owner(callback.from_user.id):
        return await callback.answer("Нет доступа.", show_alert=True)
    telegram_id = int(callback.data.split(":")[1])
    user = await queries.get_user_by_telegram_id(telegram_id)
    if not user:
        return await callback.answer("Пользователь не найден.", show_alert=True)
    await callback.message.edit_text(
        f"⚠️ Снять роль Staff с <b>{html.escape(user['nickname'])}</b>?",
        reply_markup=staff_remove_confirm_keyboard(telegram_id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("staff_remove_confirm:"))
async def execute_remove_staff(callback: CallbackQuery, bot) -> None:
    if not _is_owner(callback.from_user.id):
        return await callback.answer("Нет доступа.", show_alert=True)
    telegram_id = int(callback.data.split(":")[1])
    user = await queries.get_user_by_telegram_id(telegram_id)
    if not user:
        return await callback.answer("Пользователь не найден.", show_alert=True)
    await queries.remove_staff(user["id"])
    log_admin_action(config.owner_id, "Снятие Staff", f"{user['nickname']} ({telegram_id})")
    try:
        await bot.send_message(telegram_id, "❌ Твоя роль <b>Staff</b> снята.")
    except Exception:
        pass
    await callback.message.edit_text(
        f"✅ Роль Staff снята с <b>{html.escape(user['nickname'])}</b>.",
        reply_markup=admin_staff_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "cancel_admin_form")
async def cancel_staff_form(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    if not _is_owner(callback.from_user.id):
        return await callback.answer()
    await callback.message.edit_text("🛠 <b>Управление Staff</b>", reply_markup=admin_staff_keyboard())
    await callback.answer()
