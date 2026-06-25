"""
Управление Staff (Owner only).
"""
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext

from bot.config import config
from bot.database import queries
from bot.keyboards.admin import (
    admin_staff_keyboard, staff_list_keyboard,
    staff_member_keyboard, staff_remove_confirm_keyboard,
    cancel_admin_keyboard,
)
from bot.states.forms import ManageStaff

router = Router()


def _is_owner(uid: int) -> bool:
    return uid == config.owner_id


# ── Меню Staff ────────────────────────────────────────────────────

@router.callback_query(F.data == "admin_staff")
async def show_staff_menu(callback: CallbackQuery) -> None:
    if not _is_owner(callback.from_user.id):
        return await callback.answer("No access.", show_alert=True)
    await callback.message.edit_text(
        "\U0001f6e0 <b>Управление Staff</b>\n\nВыберите действие:",
        reply_markup=admin_staff_keyboard(),
        parse_mode="HTML",
    )
    await callback.answer()


# ── Список Staff ──────────────────────────────────────────────────

@router.callback_query(F.data == "staff_list")
async def show_staff_list(callback: CallbackQuery) -> None:
    if not _is_owner(callback.from_user.id):
        return await callback.answer("No access.", show_alert=True)
    staff = await queries.get_all_staff()
    if not staff:
        await callback.message.edit_text(
            "\U0001f6e0 <b>Список Staff</b>\n\nСписок пуст.",
            reply_markup=admin_staff_keyboard(),
            parse_mode="HTML",
        )
    else:
        await callback.message.edit_text(
            f"\U0001f6e0 <b>Список Staff</b> ({len(staff)} чел.):",
            reply_markup=staff_list_keyboard(staff),
            parse_mode="HTML",
        )
    await callback.answer()


# ── Просмотр участника ────────────────────────────────────────────

@router.callback_query(F.data.startswith("staff_view:"))
async def view_staff_member(callback: CallbackQuery) -> None:
    if not _is_owner(callback.from_user.id):
        return await callback.answer("No access.", show_alert=True)
    telegram_id = int(callback.data.split(":")[1])
    user = await queries.get_user_by_telegram_id(telegram_id)
    if not user:
        return await callback.answer("Пользователь не найден.", show_alert=True)
    stats = await queries.get_staff_stats(user["id"])
    last = stats["last_activity"] or "—"
    text = (
        f"\U0001f6e0 <b>Staff: {user['nickname']}</b>\n"
        f"@{user.get('username') or '—'} | <code>{telegram_id}</code>\n\n"
        f"\U0001f4cb Выполнено квестов: <b>{stats['completed']}</b>\n"
        f"\u2b50 Заработано баллов: <b>{stats['earned_points']:g}</b>\n"
        f"\U0001f3ab Заработано тикетов: <b>{stats['earned_tickets']:g}</b>\n"
        f"\U0001f4c5 Последняя активность: <b>{last}</b>"
    )
    await callback.message.edit_text(
        text, reply_markup=staff_member_keyboard(telegram_id), parse_mode="HTML"
    )
    await callback.answer()


# ── Рейтинг ───────────────────────────────────────────────────────

@router.callback_query(F.data == "staff_leaderboard")
async def show_leaderboard(callback: CallbackQuery) -> None:
    if not _is_owner(callback.from_user.id):
        return await callback.answer("No access.", show_alert=True)
    board = await queries.get_staff_leaderboard()
    if not board:
        text = "\U0001f3c6 <b>Рейтинг Staff</b>\n\nПока нет данных."
    else:
        medals = ["\U0001f947", "\U0001f948", "\U0001f949"]
        lines = ["\U0001f3c6 <b>Рейтинг Staff</b>\n"]
        for i, row in enumerate(board, 1):
            m = medals[i - 1] if i <= 3 else f"{i}."
            lines.append(
                f"{m} <b>{row['nickname']}</b> — "
                f"{row['completed_quests']} кв., "
                f"{row['earned_points']:g} \u2b50"
            )
        text = "\n".join(lines)
    await callback.message.edit_text(text, reply_markup=admin_staff_keyboard(), parse_mode="HTML")
    await callback.answer()


# ── Добавить Staff ────────────────────────────────────────────────

@router.callback_query(F.data == "staff_add")
async def start_add_staff(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_owner(callback.from_user.id):
        return await callback.answer("No access.", show_alert=True)
    await state.set_state(ManageStaff.waiting_user_search)
    await callback.message.edit_text(
        "\U0001f6e0 <b>Добавить Staff</b>\n\nВведите никнейм или Telegram ID пользователя:",
        reply_markup=cancel_admin_keyboard(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(ManageStaff.waiting_user_search)
async def process_add_staff(message: Message, state: FSMContext, bot) -> None:
    if not _is_owner(message.from_user.id):
        return
    query = message.text.strip()
    user = None
    if query.lstrip("-").isdigit():
        user = await queries.get_user_by_telegram_id(int(query))
    if not user:
        user = await queries.get_user_by_nickname(query)
    if not user:
        return await message.answer(
            "\u274c Пользователь не найден. Попробуйте ещё раз:",
            reply_markup=cancel_admin_keyboard(),
        )
    if user["telegram_id"] == config.owner_id:
        await state.clear()
        return await message.answer(
            "\u26a0\ufe0f Owner не может быть добавлен в Staff.",
            reply_markup=admin_staff_keyboard(),
        )
    await queries.add_staff(user["id"], granted_by=config.owner_id)
    await state.clear()
    try:
        await bot.send_message(
            user["telegram_id"],
            "\U0001f389 <b>Поздравляем!</b>\n\n"
            "Вам была выдана роль <b>Staff</b>.\n"
            "Теперь вам доступна вкладка \u00ab\U0001f4cbКвесты\u00bb.",
            parse_mode="HTML",
        )
    except Exception:
        pass
    await message.answer(
        f"\u2705 <b>{user['nickname']}</b> добавлен в Staff.",
        reply_markup=admin_staff_keyboard(),
        parse_mode="HTML",
    )


# ── Снять Staff ───────────────────────────────────────────────────

@router.callback_query(F.data.startswith("staff_remove:"))
async def confirm_remove_staff(callback: CallbackQuery) -> None:
    if not _is_owner(callback.from_user.id):
        return await callback.answer("No access.", show_alert=True)
    telegram_id = int(callback.data.split(":")[1])
    user = await queries.get_user_by_telegram_id(telegram_id)
    if not user:
        return await callback.answer("Пользователь не найден.", show_alert=True)
    await callback.message.edit_text(
        f"\u26a0\ufe0f Снять роль Staff с <b>{user['nickname']}</b>?",
        reply_markup=staff_remove_confirm_keyboard(telegram_id),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("staff_remove_confirm:"))
async def execute_remove_staff(callback: CallbackQuery, bot) -> None:
    if not _is_owner(callback.from_user.id):
        return await callback.answer("No access.", show_alert=True)
    telegram_id = int(callback.data.split(":")[1])
    user = await queries.get_user_by_telegram_id(telegram_id)
    if not user:
        return await callback.answer("Пользователь не найден.", show_alert=True)
    await queries.remove_staff(user["id"])
    try:
        await bot.send_message(
            telegram_id,
            "\u274c <b>Ваша роль Staff была снята.</b>",
            parse_mode="HTML",
        )
    except Exception:
        pass
    await callback.message.edit_text(
        f"\u2705 Роль Staff снята с <b>{user['nickname']}</b>.",
        reply_markup=admin_staff_keyboard(),
        parse_mode="HTML",
    )
    await callback.answer()


# ── Отмена формы ──────────────────────────────────────────────────

@router.callback_query(F.data == "cancel_admin_form")
async def cancel_staff_form(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    if not _is_owner(callback.from_user.id):
        return await callback.answer()
    await callback.message.edit_text(
        "\U0001f6e0 <b>Управление Staff</b>\n\nВыберите действие:",
        reply_markup=admin_staff_keyboard(),
        parse_mode="HTML",
    )
    await callback.answer()
