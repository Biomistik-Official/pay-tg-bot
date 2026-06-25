"""
Интерфейс квестов для Staff.
"""
import asyncio
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext

from bot.database import queries
from bot.keyboards.staff import (
    staff_quests_main_keyboard, active_quests_keyboard,
    quest_detail_staff_keyboard, my_quests_keyboard,
    quest_submit_keyboard, quest_submitted_keyboard,
    quest_history_keyboard, submit_content_keyboard,
    cancel_staff_keyboard,
)
from bot.states.forms import SubmitQuest

router = Router()

PAGE_SIZE = 5

REWARD_TYPES = {
    "points":            "⭐ Баллы",
    "tickets_platinum":  "💎 Платиновые тикеты",
    "tickets_gold":      "🥇 Золотые тикеты",
    "tickets_silver":    "🥈 Серебряные тикеты",
    "tickets_bronze":    "🥉 Бронзовые тикеты",
    "tickets_support":   "🎁 Тикеты поддержки",
    "tickets_help":      "💪 Хелп тикеты",
}


async def _get_user_id(telegram_id: int):
    """Возвращает (db_id, is_staff). Если не Staff — None, False."""
    user = await queries.get_user_by_telegram_id(telegram_id)
    if not user:
        return None, False
    staff_ok = await queries.is_staff(telegram_id)
    return user["id"], staff_ok


def _reward_str(reward_type: str, amount: float) -> str:
    label = REWARD_TYPES.get(reward_type, reward_type)
    return f"{amount:g} {label}"


# ── Главное меню квестов ──────────────────────────────────────────

@router.callback_query(F.data == "staff_quests_menu")
async def quests_menu(callback: CallbackQuery) -> None:
    user_id, ok = await _get_user_id(callback.from_user.id)
    if not ok:
        return await callback.answer("\u26d4 Нет доступа.", show_alert=True)
    await callback.message.edit_text(
        "\U0001f4cb <b>Квесты</b>\n\nВыберите раздел:",
        reply_markup=staff_quests_main_keyboard(),
        parse_mode="HTML",
    )
    await callback.answer()


# ── Noop (заглушка для неактивных кнопок) ────────────────────────

@router.callback_query(F.data == "staff_quest_noop")
async def quest_noop(callback: CallbackQuery) -> None:
    await callback.answer()


# ── Активные квесты ───────────────────────────────────────────────

@router.callback_query(F.data.startswith("staff_active_quests:"))
async def show_active_quests(callback: CallbackQuery) -> None:
    user_id, ok = await _get_user_id(callback.from_user.id)
    if not ok:
        return await callback.answer("\u26d4 Нет доступа.", show_alert=True)
    offset = int(callback.data.split(":")[1])
    all_quests = await queries.get_all_active_quests()
    total = len(all_quests)
    page = all_quests[offset: offset + PAGE_SIZE]
    if not page:
        await callback.message.edit_text(
            "\U0001f7e2 <b>Активные квесты</b>\n\nСейчас нет доступных квестов.",
            reply_markup=staff_quests_main_keyboard(),
            parse_mode="HTML",
        )
    else:
        await callback.message.edit_text(
            f"\U0001f7e2 <b>Активные квесты</b> ({total}):",
            reply_markup=active_quests_keyboard(page, offset, total, PAGE_SIZE),
            parse_mode="HTML",
        )
    await callback.answer()


# ── Детали квеста ─────────────────────────────────────────────────

@router.callback_query(F.data.startswith("staff_quest_detail:"))
async def show_quest_detail(callback: CallbackQuery) -> None:
    user_id, ok = await _get_user_id(callback.from_user.id)
    if not ok:
        return await callback.answer("\u26d4 Нет доступа.", show_alert=True)
    quest_id = int(callback.data.split(":")[1])
    q = await queries.get_quest_by_id(quest_id)
    if not q or q["status"] != "active":
        return await callback.answer("Квест недоступен.", show_alert=True)

    executors = await queries.count_quest_executors(quest_id)
    free_slots = q["max_executors"] - executors
    can_take = free_slots > 0
    existing = await queries.get_user_quest_assignment(quest_id, user_id)
    already_taken = existing is not None

    deadline = q["deadline"] or "—"
    reward = _reward_str(q["reward_type"], q["reward_amount"])
    slots_text = f"{executors}/{q['max_executors']}"

    text = (
        f"\U0001f4cb <b>{q['title']}</b>\n\n"
        f"\U0001f4c4 {q['description']}\n\n"
        f"\U0001f381 Награда: <b>{reward}</b>\n"
        f"\U0001f465 Исполнители: <b>{slots_text}</b>\n"
        f"\U0001f4c5 Срок: <b>{deadline}</b>"
    )
    await callback.message.edit_text(
        text,
        reply_markup=quest_detail_staff_keyboard(quest_id, can_take, already_taken),
        parse_mode="HTML",
    )
    await callback.answer()


# ── Взять квест ───────────────────────────────────────────────────

@router.callback_query(F.data.startswith("staff_take_quest:"))
async def take_quest(callback: CallbackQuery) -> None:
    user_id, ok = await _get_user_id(callback.from_user.id)
    if not ok:
        return await callback.answer("\u26d4 Нет доступа.", show_alert=True)
    quest_id = int(callback.data.split(":")[1])
    success = await queries.take_quest(quest_id, user_id)
    if not success:
        return await callback.answer("\u274c Набор завершён или вы уже взяли этот квест.", show_alert=True)
    await callback.answer("\u2705 Квест взят!", show_alert=True)
    # Обновить детали
    q = await queries.get_quest_by_id(quest_id)
    executors = await queries.count_quest_executors(quest_id)
    deadline = q["deadline"] or "—"
    reward = _reward_str(q["reward_type"], q["reward_amount"])
    slots_text = f"{executors}/{q['max_executors']}"
    text = (
        f"\U0001f4cb <b>{q['title']}</b>\n\n"
        f"\U0001f4c4 {q['description']}\n\n"
        f"\U0001f381 Награда: <b>{reward}</b>\n"
        f"\U0001f465 Исполнители: <b>{slots_text}</b>\n"
        f"\U0001f4c5 Срок: <b>{deadline}</b>"
    )
    await callback.message.edit_text(
        text,
        reply_markup=quest_detail_staff_keyboard(quest_id, False, True),
        parse_mode="HTML",
    )


# ── Мои квесты ────────────────────────────────────────────────────

@router.callback_query(F.data == "staff_my_quests")
async def my_quests(callback: CallbackQuery) -> None:
    user_id, ok = await _get_user_id(callback.from_user.id)
    if not ok:
        return await callback.answer("\u26d4 Нет доступа.", show_alert=True)
    assignments = await queries.get_user_active_assignments(user_id)
    await callback.message.edit_text(
        "\U0001f7e1 <b>Мои квесты</b>:",
        reply_markup=my_quests_keyboard(assignments),
        parse_mode="HTML",
    )
    await callback.answer()


# ── Детали своего квеста ──────────────────────────────────────────

@router.callback_query(F.data.startswith("staff_my_quest_detail:"))
async def my_quest_detail(callback: CallbackQuery) -> None:
    user_id, ok = await _get_user_id(callback.from_user.id)
    if not ok:
        return await callback.answer("\u26d4 Нет доступа.", show_alert=True)
    assignment_id = int(callback.data.split(":")[1])
    a = await queries.get_assignment_by_id(assignment_id)
    if not a or a["user_db_id"] != user_id:
        return await callback.answer("Назначение не найдено.", show_alert=True)

    reward = _reward_str(a["reward_type"], a["reward_amount"])
    status_map = {
        "taken":     "\U0001f7e1 В работе",
        "submitted": "\u23f3 На проверке",
    }
    status = status_map.get(a["status"], a["status"])
    deadline = a.get("deadline") or "—"
    text = (
        f"\U0001f4cb <b>{a['title']}</b>\n\n"
        f"\U0001f381 Награда: <b>{reward}</b>\n"
        f"\U0001f4c5 Срок: <b>{deadline}</b>\n"
        f"Статус: <b>{status}</b>"
    )
    if a["status"] == "taken":
        kb = quest_submit_keyboard(assignment_id)
    else:
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        from aiogram.types import InlineKeyboardButton
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="\u23f3 Ожидает проверки...", callback_data="staff_quest_noop"))
        builder.row(InlineKeyboardButton(text="\u2b05\ufe0f Мои квесты", callback_data="staff_my_quests"))
        kb = builder.as_markup()
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


# ── Отправить на проверку (FSM) ───────────────────────────────────

@router.callback_query(F.data.startswith("staff_submit_quest:"))
async def start_submit_quest(callback: CallbackQuery, state: FSMContext) -> None:
    user_id, ok = await _get_user_id(callback.from_user.id)
    if not ok:
        return await callback.answer("\u26d4 Нет доступа.", show_alert=True)
    assignment_id = int(callback.data.split(":")[1])
    await state.set_state(SubmitQuest.waiting_content)
    await state.update_data(assignment_id=assignment_id)
    await callback.message.edit_text(
        "\U0001f4e8 <b>Отправка на проверку</b>\n\n"
        "Отправьте текстовый отчёт и/или фото.\n"
        "<i>Если всё отправлено — нажмите «Подтвердить» после ввода.</i>",
        reply_markup=cancel_staff_keyboard(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(SubmitQuest.waiting_content)
async def receive_submit_content(message: Message, state: FSMContext) -> None:
    user_id, ok = await _get_user_id(message.from_user.id)
    if not ok:
        return
    text_content = message.text or message.caption or ""
    photo_id = None
    if message.photo:
        photo_id = message.photo[-1].file_id
    await state.update_data(submitted_text=text_content, submitted_photo=photo_id)
    await state.set_state(SubmitQuest.confirm)
    data = await state.get_data()
    assignment_id = data["assignment_id"]
    preview = text_content[:200] + ("..." if len(text_content) > 200 else "")
    photo_text = "\U0001f5bc\ufe0f Фото: прикреплено" if photo_id else ""
    reply = (
        f"\U0001f4e8 <b>Предпросмотр отчёта</b>\n\n"
        f"{preview or '(без текста)'}\n"
        f"{photo_text}\n\n"
        "Всё верно?"
    )
    await message.answer(reply, reply_markup=submit_content_keyboard(assignment_id), parse_mode="HTML")


@router.callback_query(F.data.startswith("staff_submit_confirm:"), SubmitQuest.confirm)
async def confirm_submit(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    user_id, ok = await _get_user_id(callback.from_user.id)
    if not ok:
        return await callback.answer("\u26d4 Нет доступа.", show_alert=True)
    data = await state.get_data()
    assignment_id = int(callback.data.split(":")[1])
    await state.clear()

    submitted_text = data.get("submitted_text") or ""
    submitted_photo = data.get("submitted_photo")
    a = await queries.get_assignment_by_id(assignment_id)
    if not a:
        return await callback.answer("Назначение не найдено.", show_alert=True)

    await queries.submit_quest(assignment_id, submitted_text, submitted_photo)

    # Уведомить Owner
    from bot.config import config
    from bot.keyboards.admin import quest_submission_review_keyboard
    
    reward = _reward_str(a["reward_type"], a["reward_amount"])
    kb = quest_submission_review_keyboard(assignment_id)
    
    owner_text = (
        f"\U0001f4cb <b>Квест отправлен на проверку</b>\n\n"
        f"\U0001f464 Staff: <b>{a['nickname']}</b>\n"
        f"\U0001f4dd Квест: <b>{a['title']}</b>\n"
        f"\U0001f381 Награда: <b>{reward}</b>"
    )
    if submitted_text:
        owner_text += f"\n\n\U0001f4ac Отчёт:\n{submitted_text}"
        
    try:
        if submitted_photo:
            await bot.send_photo(
                config.owner_id,
                photo=submitted_photo,
                caption=owner_text,
                reply_markup=kb,
                parse_mode="HTML"
            )
        else:
            await bot.send_message(
                config.owner_id,
                owner_text,
                reply_markup=kb,
                parse_mode="HTML"
            )
    except Exception:
        pass

    await callback.message.edit_text(
        "\u2705 <b>Квест отправлен на проверку!</b>\n\nOwner получит уведомление.",
        reply_markup=quest_submitted_keyboard(),
        parse_mode="HTML",
    )
    await callback.answer()


# ── История квестов ───────────────────────────────────────────────

@router.callback_query(F.data == "staff_quest_history")
async def show_quest_history(callback: CallbackQuery) -> None:
    user_id, ok = await _get_user_id(callback.from_user.id)
    if not ok:
        return await callback.answer("\u26d4 Нет доступа.", show_alert=True)
    history = await queries.get_user_quest_history(user_id)
    await callback.message.edit_text(
        "\U0001f4dc <b>История квестов</b>:",
        reply_markup=quest_history_keyboard(history),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("staff_history_detail:"))
async def history_detail(callback: CallbackQuery) -> None:
    user_id, ok = await _get_user_id(callback.from_user.id)
    if not ok:
        return await callback.answer("\u26d4 Нет доступа.", show_alert=True)
    assignment_id = int(callback.data.split(":")[1])
    a = await queries.get_assignment_by_id(assignment_id)
    if not a or a["user_db_id"] != user_id:
        return await callback.answer("Запись не найдена.", show_alert=True)

    reward = _reward_str(a["reward_type"], a["reward_amount"])
    status_map = {
        "approved": "\U0001f7e2 Выполнен",
        "rejected": "\U0001f534 Отклонён",
    }
    status = status_map.get(a["status"], a["status"])
    date = (a.get("reviewed_at") or "")[:10]
    reject_reason = a.get("reject_reason") or ""

    text = (
        f"\U0001f4cb <b>{a['title']}</b>\n\n"
        f"Статус: <b>{status}</b>\n"
        f"\U0001f381 Награда: <b>{reward}</b>\n"
        f"\U0001f4c5 Дата: <b>{date}</b>"
    )
    if reject_reason:
        text += f"\n\n\U0001f4ac Причина: {reject_reason}"

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="\u2b05\ufe0f Назад", callback_data="staff_quest_history"))
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("staff_abandon_quest:"))
async def abandon_quest(callback: CallbackQuery, bot: Bot) -> None:
    user_id, ok = await _get_user_id(callback.from_user.id)
    if not ok:
        return await callback.answer("⛔ Нет доступа.", show_alert=True)
    assignment_id = int(callback.data.split(":")[1])
    a = await queries.get_assignment_by_id(assignment_id)
    if not a or a["user_db_id"] != user_id:
        return await callback.answer("Назначение не найдено.", show_alert=True)
    if a["status"] != "taken":
        return await callback.answer("Нельзя отказаться от квеста на проверке или уже выполненного.", show_alert=True)

    quest_id = a["quest_id"]
    q = await queries.get_quest_by_id(quest_id)

    await queries.delete_assignment(assignment_id)

    await callback.message.edit_text(
        f"❌ Вы отказались от квеста <b>{a['title']}</b>.",
        reply_markup=staff_quests_main_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer("Вы отказались от квеста.", show_alert=True)

    # Если квест на 1 человека, оповестить весь стафф
    if q and q["max_executors"] == 1:
        staff_ids = await queries.get_staff_telegram_ids()
        reward = _reward_str(q["reward_type"], q["reward_amount"])
        deadline_val = q["deadline"] or "—"
        
        notification_text = (
            f"⚠️ <b>Квест снова доступен!</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"📌 <b>{q['title']}</b>\n\n"
            f"📝 Описание:\n{q['description']}\n\n"
            f"🎁 Награда: <b>{reward}</b>\n"
            f"👥 Макс. исполнителей: <b>{q['max_executors']}</b>\n"
            f"📅 Срок: <b>{deadline_val}</b>\n\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"Кто-то отказался от этого квеста, вы можете взять его!"
        )
        
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🔎 Открыть квест", callback_data=f"staff_quest_detail:{quest_id}")]
            ]
        )
        
        async def broadcast_abandoned():
            for uid in staff_ids:
                if uid == callback.from_user.id:
                    continue
                try:
                    await bot.send_message(
                        uid,
                        notification_text,
                        reply_markup=kb,
                        parse_mode="HTML"
                    )
                except Exception:
                    pass
                await asyncio.sleep(0.05)
                
        asyncio.create_task(broadcast_abandoned())
