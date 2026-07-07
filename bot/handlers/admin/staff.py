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
    admin_ranks_menu_keyboard, admin_ranks_list_keyboard,
    rank_pick_keyboard, rank_history_keyboard,
    admin_coefs_keyboard,
)
from bot.states.forms import ManageStaff, SetRankCoefficient
from bot.utils.ranks import (
    RANK_META, RANK_ORDER, DEFAULT_RANK,
    rank_label, rank_name,
)
from bot.utils.logger import log_admin_action
from bot.utils.formatters import format_datetime

router = Router()


def _is_owner(uid: int) -> bool:
    return uid == config.owner_id


# Меню Staff

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


# Список Staff

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


# Просмотр участника

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
    rank = await queries.get_staff_rank(user["id"])
    coef = await queries.get_rank_coefficient(rank)
    cat = await queries.get_staff_category_info(user["id"])
    cat_line = (
        f"📂 Категория: <b>{cat['name']}</b> (×{cat['coefficient']:g})"
        if cat else "📂 Категория: <i>не назначена</i>"
    )
    text = (
        f"\U0001f6e0 <b>Staff: {user['nickname']}</b>\n"
        f"@{user.get('username') or '—'} | <code>{telegram_id}</code>\n\n"
        f"🎖 Ранг: <b>{rank_label(rank)}</b>\n"
        f"📈 Коэффициент: <b>×{coef:g}</b>\n"
        f"{cat_line}\n\n"
        f"\U0001f4cb Выполнено квестов: <b>{stats['completed']}</b>\n"
        f"\u2b50 Заработано баллов: <b>{stats['earned_points']:g}</b>\n"
        f"\U0001f3ab Заработано тикетов: <b>{stats['earned_tickets']:g}</b>\n"
        f"\U0001f4c5 Последняя активность: <b>{last}</b>"
    )
    await callback.message.edit_text(
        text, reply_markup=staff_member_keyboard(telegram_id), parse_mode="HTML"
    )
    await callback.answer()


# Рейтинг

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
            r = row.get("rank") or DEFAULT_RANK
            lines.append(
                f"{m} <b>{row['nickname']}</b> ({rank_label(r)}) — "
                f"{row['completed_quests']} кв., "
                f"{row['earned_points']:g} \u2b50"
            )
        text = "\n".join(lines)
    await callback.message.edit_text(text, reply_markup=admin_staff_keyboard(), parse_mode="HTML")
    await callback.answer()


# Добавить Staff

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


# Снять Staff

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


# Отмена формы

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


#  Управление рангами Staff (Owner only)

@router.callback_query(F.data == "admin_ranks")
async def show_ranks_menu(callback: CallbackQuery) -> None:
    """Меню «Управление ролями Staff»."""
    if not _is_owner(callback.from_user.id):
        return await callback.answer("No access.", show_alert=True)
    lines = ["🎖 <b>Управление ролями Staff</b>\n\nРанги:"]
    coefs = await queries.get_all_rank_coefficients()
    for rank in RANK_ORDER:
        meta = RANK_META[rank]
        c = coefs.get(rank, meta["default_coef"])
        lines.append(f"• {meta['emoji']} <b>{meta['name']}</b> — ×{c:g}")
    lines.append(
        "\nВыберите ранг — увидите список Staff с этим рангом, "
        "или откройте общий список Staff для назначения."
    )
    await callback.message.edit_text(
        "\n".join(lines),
        reply_markup=admin_ranks_menu_keyboard(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_ranks_list:"))
async def show_ranks_list(callback: CallbackQuery) -> None:
    """Список Staff (все или отфильтрованный по рангу)."""
    if not _is_owner(callback.from_user.id):
        return await callback.answer("No access.", show_alert=True)
    which = callback.data.split(":")[1]
    all_staff = await queries.get_all_staff()
    if which == "all":
        filtered = all_staff
        title = "Все Staff"
    else:
        if which not in RANK_META:
            return await callback.answer("Неизвестный ранг.", show_alert=True)
        filtered = [m for m in all_staff if (m.get("rank") or DEFAULT_RANK) == which]
        title = f"Staff — {RANK_META[which]['emoji']} {RANK_META[which]['name']}"

    if not filtered:
        await callback.message.edit_text(
            f"🎖 <b>{title}</b>\n\nСписок пуст.",
            reply_markup=admin_ranks_menu_keyboard(),
            parse_mode="HTML",
        )
    else:
        await callback.message.edit_text(
            f"🎖 <b>{title}</b> ({len(filtered)}):",
            reply_markup=admin_ranks_list_keyboard(filtered, which),
            parse_mode="HTML",
        )
    await callback.answer()


@router.callback_query(F.data.startswith("staff_set_rank:"))
async def pick_rank_for_staff(callback: CallbackQuery) -> None:
    """Выбор нового ранга Staff."""
    if not _is_owner(callback.from_user.id):
        return await callback.answer("No access.", show_alert=True)
    telegram_id = int(callback.data.split(":")[1])
    user = await queries.get_user_by_telegram_id(telegram_id)
    if not user:
        return await callback.answer("Пользователь не найден.", show_alert=True)
    staff = await queries.get_staff_by_user_id(user["id"])
    if not staff:
        return await callback.answer("Пользователь не Staff.", show_alert=True)
    current = staff.get("rank") or DEFAULT_RANK
    coef = await queries.get_rank_coefficient(current)
    text = (
        f"🎖 <b>Ранг Staff: {user['nickname']}</b>\n\n"
        f"Текущий ранг: <b>{rank_label(current)}</b>\n"
        f"Коэффициент: <b>×{coef:g}</b>\n\n"
        f"Выберите новый ранг:"
    )
    await callback.message.edit_text(
        text,
        reply_markup=rank_pick_keyboard(telegram_id, current),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("staff_rank_apply:"))
async def apply_rank(callback: CallbackQuery, bot) -> None:
    """Применить выбранный ранг для Staff."""
    if not _is_owner(callback.from_user.id):
        return await callback.answer("No access.", show_alert=True)
    _, tg_str, new_rank = callback.data.split(":")
    telegram_id = int(tg_str)
    if new_rank not in RANK_META:
        return await callback.answer("Неизвестный ранг.", show_alert=True)

    user = await queries.get_user_by_telegram_id(telegram_id)
    if not user:
        return await callback.answer("Пользователь не найден.", show_alert=True)
    staff = await queries.get_staff_by_user_id(user["id"])
    if not staff:
        return await callback.answer("Пользователь не Staff.", show_alert=True)

    old_rank = staff.get("rank") or DEFAULT_RANK
    if old_rank == new_rank:
        return await callback.answer("Этот ранг уже установлен.", show_alert=True)

    await queries.set_staff_rank(user["id"], new_rank, changed_by=callback.from_user.id)
    log_admin_action(
        callback.from_user.id,
        "Изменение ранга Staff",
        f"user={user['nickname']} ({telegram_id}) {old_rank} → {new_rank}",
    )

    coef = await queries.get_rank_coefficient(new_rank)
    try:
        await bot.send_message(
            telegram_id,
            f"🎖 <b>Ваш ранг Staff изменён.</b>\n\n"
            f"Было: <b>{rank_label(old_rank)}</b>\n"
            f"Стало: <b>{rank_label(new_rank)}</b>\n"
            f"📈 Коэффициент награды: <b>×{coef:g}</b>",
            parse_mode="HTML",
        )
    except Exception:
        pass

    await callback.answer(f"✅ Ранг: {rank_label(new_rank)}", show_alert=True)
    await callback.message.edit_text(
        f"✅ <b>Ранг обновлён:</b> {rank_label(new_rank)}\n\n"
        f"Пользователь: <b>{user['nickname']}</b>\n"
        f"Было: {rank_label(old_rank)} → Стало: {rank_label(new_rank)}",
        reply_markup=rank_pick_keyboard(telegram_id, new_rank),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("staff_rank_history:"))
async def show_rank_history(callback: CallbackQuery) -> None:
    """История изменений ранга Staff."""
    if not _is_owner(callback.from_user.id):
        return await callback.answer("No access.", show_alert=True)
    telegram_id = int(callback.data.split(":")[1])
    user = await queries.get_user_by_telegram_id(telegram_id)
    if not user:
        return await callback.answer("Пользователь не найден.", show_alert=True)

    history = await queries.get_staff_rank_history(user["id"], limit=30)
    if not history:
        text = f"🕓 <b>История ранга: {user['nickname']}</b>\n\nЗаписей ещё нет."
    else:
        lines = [f"🕓 <b>История ранга: {user['nickname']}</b>\n"]
        for h in history:
            date = format_datetime(h["changed_at"])
            actor = h.get("changed_by_nickname") or (str(h.get("changed_by") or "—"))
            if h.get("old_rank"):
                lines.append(
                    f"📅 {date}\n"
                    f"   {rank_label(h['old_rank'])} → {rank_label(h['new_rank'])}\n"
                    f"   👑 {actor}"
                )
            else:
                lines.append(
                    f"📅 {date}\n"
                    f"   Назначен: {rank_label(h['new_rank'])}\n"
                    f"   👑 {actor}"
                )
        text = "\n\n".join(lines)

    await callback.message.edit_text(
        text,
        reply_markup=rank_history_keyboard(telegram_id),
        parse_mode="HTML",
    )
    await callback.answer()


#  Коэффициенты рангов Staff (Owner only)

@router.callback_query(F.data == "admin_coefs")
async def show_coefs_menu(callback: CallbackQuery) -> None:
    """Меню коэффициентов рангов Staff."""
    if not _is_owner(callback.from_user.id):
        return await callback.answer("No access.", show_alert=True)
    coefs = await queries.get_all_rank_coefficients()
    lines = ["⚙️ <b>Коэффициенты Staff</b>\n"]
    for rank in RANK_ORDER:
        meta = RANK_META[rank]
        c = coefs.get(rank, meta["default_coef"])
        lines.append(f"{meta['emoji']} <b>{meta['name']}</b> — ×{c:g}")
    lines.append(
        "\nНажмите на ранг, чтобы изменить множитель.\n"
        "<i>Изменения применяются сразу ко всем новым квестам.</i>"
    )
    await callback.message.edit_text(
        "\n".join(lines),
        reply_markup=admin_coefs_keyboard(coefs),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_coef_edit:"))
async def start_coef_edit(callback: CallbackQuery, state: FSMContext) -> None:
    """Запросить новое значение коэффициента для ранга."""
    if not _is_owner(callback.from_user.id):
        return await callback.answer("No access.", show_alert=True)
    rank = callback.data.split(":")[1]
    if rank not in RANK_META:
        return await callback.answer("Неизвестный ранг.", show_alert=True)
    current = await queries.get_rank_coefficient(rank)
    await state.set_state(SetRankCoefficient.waiting_value)
    await state.update_data(rank=rank)
    await callback.message.edit_text(
        f"⚙️ <b>Коэффициент — {rank_label(rank)}</b>\n\n"
        f"Текущее значение: <b>×{current:g}</b>\n\n"
        f"Введите новый множитель (например, 1.5):",
        reply_markup=cancel_admin_keyboard(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(SetRankCoefficient.waiting_value)
async def apply_coef_edit(message: Message, state: FSMContext) -> None:
    """Применить введённое значение коэффициента."""
    if not _is_owner(message.from_user.id):
        return
    data = await state.get_data()
    rank = data.get("rank")
    if rank not in RANK_META:
        await state.clear()
        return
    try:
        value = float(message.text.strip().replace(",", "."))
        if value <= 0:
            raise ValueError
    except ValueError:
        return await message.answer(
            "⚠️ Введите положительное число (например, 1.5).",
            reply_markup=cancel_admin_keyboard(),
        )

    old = await queries.get_rank_coefficient(rank)
    await queries.set_rank_coefficient(rank, value)
    await state.clear()
    log_admin_action(
        message.from_user.id,
        "Изменение коэффициента ранга",
        f"rank={rank} {old:g} → {value:g}",
    )

    coefs = await queries.get_all_rank_coefficients()
    lines = [
        f"✅ Коэффициент <b>{rank_label(rank)}</b>: <b>×{value:g}</b>\n",
        "⚙️ <b>Коэффициенты Staff</b>\n",
    ]
    for r in RANK_ORDER:
        meta = RANK_META[r]
        c = coefs.get(r, meta["default_coef"])
        lines.append(f"{meta['emoji']} <b>{meta['name']}</b> — ×{c:g}")
    await message.answer(
        "\n".join(lines),
        reply_markup=admin_coefs_keyboard(coefs),
        parse_mode="HTML",
    )
