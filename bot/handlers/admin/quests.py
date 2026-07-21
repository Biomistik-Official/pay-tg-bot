"""
Управление квестами (Owner only).
"""
import asyncio
import html
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext

from bot.config import config
from bot.database import queries
from bot.keyboards.admin import (
    admin_quests_keyboard, quest_list_admin_keyboard,
    quest_detail_admin_keyboard, quest_edit_field_keyboard,
    quest_delete_confirm_keyboard, quest_submission_review_keyboard,
    submissions_nav_keyboard, cancel_admin_keyboard,
)
from bot.states.forms import CreateQuest, EditQuest, RejectQuest
from bot.utils.ranks import apply_coefficient
from bot.utils.logger import log_admin_action

router = Router()

REWARD_TYPES = {
    "points":            "\u2b50 Баллы",
    "tickets_platinum":  "\U0001f48e Платиновые тикеты",
    "tickets_gold":      "\U0001f947 Золотые тикеты",
    "tickets_silver":    "\U0001f948 Серебряные тикеты",
    "tickets_bronze":    "\U0001f949 Бронзовые тикеты",
    "tickets_support":   "\U0001f381 Тикеты поддержки",
}

# Способы начисления награды
REWARD_MODES = {
    "flat":        "⭐ Обычная награда",
    "coefficient": "\U0001f4c8 Награда с коэффициентом",
}

REPEAT_MODES = {
    "single": "1 раз для каждого человека",
    "multiple": "Можно выполнять несколько раз",
}


def _is_owner(uid: int) -> bool:
    return uid == config.owner_id


def _reward_mode_label(mode: str) -> str:
    return REWARD_MODES.get(mode, REWARD_MODES["flat"])


async def _edit_or_reply(callback: CallbackQuery, text: str, reply_markup=None) -> None:
    if callback.message.photo or callback.message.video:
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.message.answer(text, reply_markup=reply_markup, parse_mode="HTML")
    else:
        try:
            await callback.message.edit_text(text, reply_markup=reply_markup, parse_mode="HTML")
        except Exception:
            await callback.message.answer(text, reply_markup=reply_markup, parse_mode="HTML")


def _reward_label(reward_type: str, amount: float) -> str:
    label = REWARD_TYPES.get(reward_type, reward_type)
    return f"{amount:g} {label}"


def _quest_text(q: dict) -> str:
    status = "\U0001f7e2 Активен" if q["status"] == "active" else "\U0001f534 Закрыт"
    deadline = q["deadline"] or "—"
    reward = _reward_label(q["reward_type"], q["reward_amount"])
    mode = _reward_mode_label(q.get("reward_mode", "flat"))
    repeat_mode = REPEAT_MODES["multiple"] if q.get("repeatable") else REPEAT_MODES["single"]
    return (
        f"\U0001f4cb <b>{q['title']}</b>\n\n"
        f"\U0001f4c4 {q['description']}\n\n"
        f"\U0001f381 Награда: <b>{reward}</b>\n"
        f"\U0001f3af Тип награды: <b>{mode}</b>\n"
        f"\U0001f465 Макс. исполнителей: <b>{q['max_executors']}</b>\n"
        f"🔁 Выполнение: <b>{repeat_mode}</b>\n"
        f"\U0001f4c5 Срок: <b>{deadline}</b>\n"
        f"Статус: <b>{status}</b>"
    )


# Меню

@router.callback_query(F.data == "admin_quests")
async def show_quests_menu(callback: CallbackQuery) -> None:
    if not _is_owner(callback.from_user.id):
        return await callback.answer("No access.", show_alert=True)
    await _edit_or_reply(
        callback,
        "\U0001f4cb <b>Управление квестами</b>\n\nВыберите действие:",
        reply_markup=admin_quests_keyboard(),
    )
    await callback.answer()


# Список квестов

@router.callback_query(F.data == "quest_list")
async def show_quest_list(callback: CallbackQuery) -> None:
    if not _is_owner(callback.from_user.id):
        return await callback.answer("No access.", show_alert=True)
    quests = await queries.get_all_quests()
    if not quests:
        await _edit_or_reply(
            callback,
            "\U0001f4cb <b>Квесты</b>\n\nКвестов пока нет.",
            reply_markup=admin_quests_keyboard(),
        )
    else:
        await _edit_or_reply(
            callback,
            f"\U0001f4cb <b>Все квесты</b> ({len(quests)}):",
            reply_markup=quest_list_admin_keyboard(quests),
        )
    await callback.answer()


# Детали квеста

@router.callback_query(F.data.startswith("quest_detail:"))
async def show_quest_detail(callback: CallbackQuery) -> None:
    if not _is_owner(callback.from_user.id):
        return await callback.answer("No access.", show_alert=True)
    quest_id = int(callback.data.split(":")[1])
    q = await queries.get_quest_by_id(quest_id)
    if not q:
        return await callback.answer("Квест не найден.", show_alert=True)
    await _edit_or_reply(
        callback,
        _quest_text(q),
        reply_markup=quest_detail_admin_keyboard(quest_id, q["status"] == "active"),
    )
    await callback.answer()


# Статистика квеста

@router.callback_query(F.data.startswith("quest_stats:"))
async def show_quest_stats(callback: CallbackQuery) -> None:
    if not _is_owner(callback.from_user.id):
        return await callback.answer("No access.", show_alert=True)
    quest_id = int(callback.data.split(":")[1])
    q = await queries.get_quest_by_id(quest_id)
    if not q:
        return await callback.answer("Квест не найден.", show_alert=True)
    s = await queries.get_quest_stats(quest_id)
    
    reward = _reward_label(q["reward_type"], q["reward_amount"])
    executors = await queries.get_quest_executors(quest_id)
    status_labels = {
        "taken": "🟡 в работе",
        "submitted": "⏳ на проверке",
        "approved": "✅ одобрено",
        "rejected": "❌ отклонено",
    }
    
    executors_list = []
    for idx, e in enumerate(executors, 1):
        if e.get("username"):
            tag = f"@{e['username']}"
        else:
            escaped_nickname = html.escape(e['nickname'])
            tag = f"<a href=\"tg://user?id={e['telegram_id']}\">{escaped_nickname}</a>"
        status = status_labels.get(e["status"], e["status"])
        executors_list.append(f"{idx}. {tag} — {status}")
    
    executors_str = "\n".join(executors_list) if executors_list else "—"
    
    text = (
        f"\U0001f4ca <b>Статистика: {q['title']}</b>\n\n"
        f"\U0001f381 Награда: <b>{reward}</b>\n\n"
        f"Взято: <b>{s['taken']}</b>\n"
        f"На проверке: <b>{s['submitted']}</b>\n"
        f"\u2705 Одобрено: <b>{s['approved']}</b>\n"
        f"\u274c Отклонено: <b>{s['rejected']}</b>\n"
        f"Всего: <b>{s['total']}</b>\n\n"
        f"Взяли квест:\n{executors_str}"
    )
    await _edit_or_reply(
        callback,
        text,
        reply_markup=quest_detail_admin_keyboard(quest_id, q["status"] == "active"),
    )
    await callback.answer()


# Закрыть квест

@router.callback_query(F.data.startswith("quest_close:"))
async def close_quest(callback: CallbackQuery) -> None:
    if not _is_owner(callback.from_user.id):
        return await callback.answer("No access.", show_alert=True)
    quest_id = int(callback.data.split(":")[1])
    await queries.close_quest(quest_id)
    await callback.answer("\U0001f512 Квест закрыт.", show_alert=True)
    q = await queries.get_quest_by_id(quest_id)
    await _edit_or_reply(
        callback,
        _quest_text(q),
        reply_markup=quest_detail_admin_keyboard(quest_id, False),
    )


# Удалить квест

@router.callback_query(F.data.startswith("quest_delete:"))
async def ask_delete_quest(callback: CallbackQuery) -> None:
    if not _is_owner(callback.from_user.id):
        return await callback.answer("No access.", show_alert=True)
    quest_id = int(callback.data.split(":")[1])
    q = await queries.get_quest_by_id(quest_id)
    if not q:
        return await callback.answer("Квест не найден.", show_alert=True)
    await _edit_or_reply(
        callback,
        f"\u26a0\ufe0f Удалить квест <b>{q['title']}</b>? Это действие необратимо.",
        reply_markup=quest_delete_confirm_keyboard(quest_id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("quest_delete_confirm:"))
async def confirm_delete_quest(callback: CallbackQuery) -> None:
    if not _is_owner(callback.from_user.id):
        return await callback.answer("No access.", show_alert=True)
    quest_id = int(callback.data.split(":")[1])
    await queries.delete_quest(quest_id)
    await _edit_or_reply(
        callback,
        "\u2705 Квест удалён.",
        reply_markup=admin_quests_keyboard(),
    )
    await callback.answer()


# Создать квест (FSM)

@router.callback_query(F.data == "quest_create")
async def start_create_quest(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_owner(callback.from_user.id):
        return await callback.answer("No access.", show_alert=True)
    await state.set_state(CreateQuest.waiting_title)
    await _edit_or_reply(
        callback,
        "\U0001f4dd <b>Создание квеста</b>\n\nШаг 1/8 — Введите <b>название</b> квеста:",
        reply_markup=cancel_admin_keyboard(),
    )
    await callback.answer()


@router.message(CreateQuest.waiting_title)
async def cq_title(message: Message, state: FSMContext) -> None:
    if not _is_owner(message.from_user.id):
        return
    title = message.text.strip()
    if len(title) < 3:
        return await message.answer("\u26a0\ufe0f Минимум 3 символа.", reply_markup=cancel_admin_keyboard())
    await state.update_data(title=title)
    await state.set_state(CreateQuest.waiting_description)
    await message.answer(
        "Шаг 2/8 — Введите <b>описание</b> квеста:",
        reply_markup=cancel_admin_keyboard(),
        parse_mode="HTML",
    )


@router.message(CreateQuest.waiting_description)
async def cq_description(message: Message, state: FSMContext) -> None:
    if not _is_owner(message.from_user.id):
        return
    await state.update_data(description=message.text.strip())
    await state.set_state(CreateQuest.waiting_reward_type)
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    for key, label in REWARD_TYPES.items():
        builder.row(InlineKeyboardButton(text=label, callback_data=f"cq_rtype:{key}"))
    builder.row(InlineKeyboardButton(text="\u274c Отмена", callback_data="cancel_admin_form"))
    await message.answer(
        "Шаг 3/8 — Выберите <b>тип награды</b>:",
        reply_markup=builder.as_markup(),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("cq_rtype:"))
async def cq_reward_type(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_owner(callback.from_user.id):
        return await callback.answer("No access.", show_alert=True)
    rtype = callback.data.split(":")[1]
    await state.update_data(reward_type=rtype)
    await state.set_state(CreateQuest.waiting_reward_amount)
    await _edit_or_reply(
        callback,
        "Шаг 4/8 — Введите <b>количество</b> награды (число):",
        reply_markup=cancel_admin_keyboard(),
    )
    await callback.answer()


@router.message(CreateQuest.waiting_reward_amount)
async def cq_reward_amount(message: Message, state: FSMContext) -> None:
    if not _is_owner(message.from_user.id):
        return
    try:
        amount = float(message.text.strip().replace(",", "."))
        if amount <= 0:
            raise ValueError
    except ValueError:
        return await message.answer("\u26a0\ufe0f Введите положительное число.", reply_markup=cancel_admin_keyboard())
    await state.update_data(reward_amount=amount)
    await state.set_state(CreateQuest.waiting_reward_mode)
    from aiogram.types import InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    for key, label in REWARD_MODES.items():
        builder.row(InlineKeyboardButton(text=label, callback_data=f"cq_rmode:{key}"))
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_admin_form"))
    await message.answer(
        "Шаг 5/8 — Выберите <b>тип награды</b>:\n\n"
        "⭐ <b>Обычная награда</b> — все Staff получают одинаковую награду.\n"
        "\U0001f4c8 <b>Награда с коэффициентом</b> — итоговая награда = базовая × коэффициент ранга Staff.",
        reply_markup=builder.as_markup(),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("cq_rmode:"), CreateQuest.waiting_reward_mode)
async def cq_reward_mode(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_owner(callback.from_user.id):
        return await callback.answer("No access.", show_alert=True)
    mode = callback.data.split(":")[1]
    if mode not in REWARD_MODES:
        mode = "flat"
    await state.update_data(reward_mode=mode)
    await state.set_state(CreateQuest.waiting_max_executors)
    await _edit_or_reply(
        callback,
        "Шаг 6/8 — Введите <b>максимальное количество исполнителей</b>:",
        reply_markup=cancel_admin_keyboard(),
    )
    await callback.answer()


@router.message(CreateQuest.waiting_max_executors)
async def cq_max_exec(message: Message, state: FSMContext) -> None:
    if not _is_owner(message.from_user.id):
        return
    try:
        n = int(message.text.strip())
        if n < 1:
            raise ValueError
    except ValueError:
        return await message.answer("\u26a0\ufe0f Введите целое число >= 1.", reply_markup=cancel_admin_keyboard())
    await state.update_data(max_executors=n)
    await state.set_state(CreateQuest.waiting_repeat_mode)
    from aiogram.types import InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    for key, label in REPEAT_MODES.items():
        builder.row(InlineKeyboardButton(text=label, callback_data=f"cq_repeat:{key}"))
    builder.row(InlineKeyboardButton(text="\u274c Отмена", callback_data="cancel_admin_form"))
    await message.answer(
        "Шаг 7/8 — Выберите, сможет ли один человек выполнять квест повторно:\n\n"
        "Для повторяемого квеста лимит исполнителей действует одновременно.",
        reply_markup=builder.as_markup(),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("cq_repeat:"), CreateQuest.waiting_repeat_mode)
async def cq_repeat_mode(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_owner(callback.from_user.id):
        return await callback.answer("No access.", show_alert=True)
    mode = callback.data.split(":")[1]
    if mode not in REPEAT_MODES:
        mode = "single"
    await state.update_data(repeatable=mode == "multiple")
    await state.set_state(CreateQuest.waiting_deadline)
    from aiogram.types import InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="\u23ed\ufe0f Без срока", callback_data="cq_no_deadline"))
    builder.row(InlineKeyboardButton(text="\u274c Отмена", callback_data="cancel_admin_form"))
    await _edit_or_reply(
        callback,
        "Шаг 8/8 — Введите <b>срок выполнения</b> (например, 30.06.2025) или нажмите «Без срока»:",
        reply_markup=builder.as_markup(),
    )
    await callback.answer()


@router.callback_query(F.data == "cq_no_deadline")
async def cq_no_deadline(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    if not _is_owner(callback.from_user.id):
        return await callback.answer("No access.", show_alert=True)
    await _finalize_quest(callback.message, state, deadline=None, bot=bot)
    await callback.answer()


@router.message(CreateQuest.waiting_deadline)
async def cq_deadline(message: Message, state: FSMContext, bot: Bot) -> None:
    if not _is_owner(message.from_user.id):
        return
    await _finalize_quest(message, state, deadline=message.text.strip(), bot=bot)


async def _finalize_quest(target, state: FSMContext, deadline, bot: Bot) -> None:
    data = await state.get_data()
    await state.clear()
    quest_id = await queries.create_quest(
        title=data["title"],
        description=data["description"],
        reward_type=data["reward_type"],
        reward_amount=data["reward_amount"],
        max_executors=data["max_executors"],
        deadline=deadline,
        created_by=config.owner_id,
        reward_mode=data.get("reward_mode", "flat"),
        repeatable=data.get("repeatable", False),
    )
    q = await queries.get_quest_by_id(quest_id)
    if hasattr(target, "answer"):
        await target.answer(
            f"\u2705 Квест <b>{q['title']}</b> создан!\n\n" + _quest_text(q),
            reply_markup=admin_quests_keyboard(),
            parse_mode="HTML",
        )
    else:
        await target.edit_text(
            f"\u2705 Квест создан!\n\n" + _quest_text(q),
            reply_markup=admin_quests_keyboard(),
            parse_mode="HTML",
        )

    # Notify staff
    try:
        staff_ids = await queries.get_staff_telegram_ids()
        if staff_ids:
            reward = _reward_label(q["reward_type"], q["reward_amount"])
            if q.get("reward_mode") == "coefficient":
                reward += " × коэффициент ранга"
            deadline_val = q["deadline"] or "—"

            notification_text = (
                f"🆕 <b>Появился новый квест!</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n\n"
                f"📌 <b>{q['title']}</b>\n\n"
                f"📝 Описание:\n{q['description']}\n\n"
                f"🎁 Награда: <b>{reward}</b>\n"
                f"👥 Макс. исполнителей: <b>{q['max_executors']}</b>\n"
                f"🔁 Выполнение: <b>{REPEAT_MODES['multiple'] if q.get('repeatable') else REPEAT_MODES['single']}</b>\n"
                f"📅 Срок: <b>{deadline_val}</b>\n\n"
                f"━━━━━━━━━━━━━━━━━━"
            )
            
            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
            kb = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="🔎 Открыть квест", callback_data=f"staff_quest_detail:{quest_id}")]
                ]
            )
            
            async def broadcast_quest():
                for uid in staff_ids:
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
            
            asyncio.create_task(broadcast_quest())
    except Exception:
        pass


# Редактировать квест

@router.callback_query(F.data.startswith("quest_edit:"))
async def start_edit_quest(callback: CallbackQuery) -> None:
    if not _is_owner(callback.from_user.id):
        return await callback.answer("No access.", show_alert=True)
    quest_id = int(callback.data.split(":")[1])
    await _edit_or_reply(
        callback,
        "\u270f\ufe0f <b>Редактирование квеста</b>\n\nКакое поле изменить?",
        reply_markup=quest_edit_field_keyboard(quest_id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("quest_edit_field:"))
async def pick_edit_field(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_owner(callback.from_user.id):
        return await callback.answer("No access.", show_alert=True)
    _, quest_id_str, field = callback.data.split(":")
    quest_id = int(quest_id_str)
    await state.set_state(EditQuest.waiting_new_value)
    await state.update_data(quest_id=quest_id, field=field)
    labels = {
        "title": "название",
        "description": "описание",
        "reward_amount": "количество награды",
        "max_executors": "максимум исполнителей",
        "deadline": "срок (или '-' чтобы убрать)",
    }
    await _edit_or_reply(
        callback,
        f"\u270f\ufe0f Введите новое <b>{labels.get(field, field)}</b>:",
        reply_markup=cancel_admin_keyboard(),
    )
    await callback.answer()


@router.message(EditQuest.waiting_new_value)
async def apply_edit_field(message: Message, state: FSMContext) -> None:
    if not _is_owner(message.from_user.id):
        return
    data = await state.get_data()
    quest_id = data["quest_id"]
    field = data["field"]
    raw = message.text.strip()
    value = raw

    if field in ("reward_amount",):
        try:
            value = float(raw.replace(",", "."))
            if value <= 0:
                raise ValueError
        except ValueError:
            return await message.answer("\u26a0\ufe0f Введите положительное число.", reply_markup=cancel_admin_keyboard())
    elif field == "max_executors":
        try:
            value = int(raw)
            if value < 1:
                raise ValueError
        except ValueError:
            return await message.answer("\u26a0\ufe0f Введите целое число >= 1.", reply_markup=cancel_admin_keyboard())
    elif field == "deadline" and raw == "-":
        value = None

    await queries.update_quest(quest_id, **{field: value})
    await state.clear()
    q = await queries.get_quest_by_id(quest_id)
    await message.answer(
        f"\u2705 Поле обновлено!\n\n" + _quest_text(q),
        reply_markup=quest_detail_admin_keyboard(quest_id, q["status"] == "active"),
        parse_mode="HTML",
    )


# Переключить тип награды (обычная / с коэффициентом)

@router.callback_query(F.data.startswith("quest_toggle_mode:"))
async def toggle_reward_mode(callback: CallbackQuery) -> None:
    if not _is_owner(callback.from_user.id):
        return await callback.answer("No access.", show_alert=True)
    quest_id = int(callback.data.split(":")[1])
    q = await queries.get_quest_by_id(quest_id)
    if not q:
        return await callback.answer("Квест не найден.", show_alert=True)
    new_mode = "coefficient" if (q.get("reward_mode") or "flat") == "flat" else "flat"
    await queries.update_quest(quest_id, reward_mode=new_mode)
    await callback.answer(f"Тип награды: {_reward_mode_label(new_mode)}", show_alert=True)
    q = await queries.get_quest_by_id(quest_id)
    await _edit_or_reply(
        callback,
        _quest_text(q),
        reply_markup=quest_detail_admin_keyboard(quest_id, q["status"] == "active"),
    )


@router.callback_query(F.data.startswith("quest_toggle_repeat:"))
async def toggle_repeat_mode(callback: CallbackQuery) -> None:
    if not _is_owner(callback.from_user.id):
        return await callback.answer("No access.", show_alert=True)
    quest_id = int(callback.data.split(":")[1])
    q = await queries.get_quest_by_id(quest_id)
    if not q:
        return await callback.answer("Квест не найден.", show_alert=True)
    repeatable = not bool(q.get("repeatable"))
    await queries.update_quest(quest_id, repeatable=int(repeatable))
    await callback.answer(
        f"Выполнение: {REPEAT_MODES['multiple'] if repeatable else REPEAT_MODES['single']}",
        show_alert=True,
    )
    q = await queries.get_quest_by_id(quest_id)
    await _edit_or_reply(
        callback,
        _quest_text(q),
        reply_markup=quest_detail_admin_keyboard(quest_id, q["status"] == "active"),
    )


# Проверка квестов

@router.callback_query(F.data.in_({"quest_submissions"}) | F.data.startswith("quest_submissions:"))
async def show_submissions(callback: CallbackQuery) -> None:
    if not _is_owner(callback.from_user.id):
        return await callback.answer("No access.", show_alert=True)
    parts = callback.data.split(":")
    offset = int(parts[1]) if len(parts) > 1 else 0
    submissions = await queries.get_submitted_assignments()
    if not submissions:
        await _edit_or_reply(
            callback,
            "\u23f3 <b>На проверке</b>\n\nНет квестов, ожидающих проверки.",
            reply_markup=admin_quests_keyboard(),
        )
        return await callback.answer()
    a = submissions[offset]
    reward = _reward_label(a["reward_type"], a["reward_amount"])
    text = (
        f"\U0001f4cb <b>Квест на проверке</b> [{offset + 1}/{len(submissions)}]\n\n"
        f"\U0001f464 Пользователь: <b>{html.escape(a['nickname'])}</b> (@{html.escape(a.get('username') or '—')})\n"
        f"\U0001f4dd Квест: <b>{html.escape(a['title'])}</b>\n"
        f"\U0001f381 Награда: <b>{reward}</b>\n"
    )
    if a.get("submitted_text"):
        text += f"\n\U0001f4ac Отчёт:\n{html.escape(a['submitted_text'])}"
    await _edit_or_reply(
        callback,
        text,
        reply_markup=quest_submission_review_keyboard(a["id"]),
    )
    # Доказательство отправляется отдельным сообщением
    if a.get("submitted_photo"):
        try:
            await callback.message.answer_photo(a["submitted_photo"])
        except Exception:
            pass
    elif a.get("submitted_video"):
        try:
            await callback.message.answer_video(a["submitted_video"])
        except Exception:
            pass
    await callback.answer()


# Одобрить

@router.callback_query(F.data.startswith("quest_approve:"))
async def approve_quest(callback: CallbackQuery, bot) -> None:
    if not _is_owner(callback.from_user.id):
        return await callback.answer("No access.", show_alert=True)
    assignment_id = int(callback.data.split(":")[1])
    a = await queries.get_assignment_by_id(assignment_id)
    if not a:
        return await callback.answer("Назначение не найдено.", show_alert=True)
    if a["status"] != "submitted":
        return await callback.answer("Уже обработано.", show_alert=True)

    await queries.approve_assignment(assignment_id, reviewed_by=config.owner_id)

    # Проверить, закрывать ли квест
    quest_id = a["quest_id"]
    q = await queries.get_quest_by_id(quest_id)
    if q and not q.get("repeatable"):
        q_stats = await queries.get_quest_stats(quest_id)
        if q_stats["approved"] >= q["max_executors"]:
            await queries.close_quest(quest_id)

    # Начислить награду — с учётом ранга, если тип награды «с коэффициентом»
    reward_type = a["reward_type"]
    base_amount = a["reward_amount"]
    user_db_id = a["user_db_id"]
    reward_mode = a.get("reward_mode") or "flat"

    if reward_mode == "coefficient":
        rank = await queries.get_staff_rank(user_db_id)
        coefficient = await queries.get_rank_coefficient(rank)
        final_amount = apply_coefficient(reward_type, base_amount, coefficient)
    else:
        rank = None
        coefficient = 1.0
        final_amount = base_amount

    await queries.update_user_balance(user_db_id, reward_type, "add", final_amount)
    reason = f"Награда за квест: {a['title']}"
    if reward_mode == "coefficient":
        reason += f" (×{coefficient:g})"
    await queries.add_transaction(
        user_id=user_db_id,
        currency_type=reward_type,
        operation="add",
        amount=final_amount,
        reason=reason,
        performed_by=config.owner_id,
    )
    # Сохранить применённый коэффициент и фактическую награду (журнал по квесту)
    await queries.record_assignment_payout(assignment_id, coefficient, final_amount)

    reward_label = _reward_label(reward_type, final_amount)
    r_icon = "\u2b50" if reward_type == "points" else "\U0001f3ab"
    try:
        await bot.send_message(
            a["user_telegram_id"],
            f"\U0001f389 <b>Квест принят!</b>\n\n"
            f"Квест: <b>{a['title']}</b>\n\n"
            f"Вам начислено:\n{r_icon} <b>{reward_label}</b>",
            parse_mode="HTML",
        )
    except Exception:
        pass

    text = f"\u2705 Квест одобрен! Награда начислена <b>{a['nickname']}</b>."
    try:
        if callback.message.photo or callback.message.video:
            await callback.message.edit_caption(
                caption=text,
                reply_markup=admin_quests_keyboard(),
                parse_mode="HTML"
            )
        else:
            await callback.message.edit_text(
                text,
                reply_markup=admin_quests_keyboard(),
                parse_mode="HTML"
            )
    except Exception:
        await callback.message.answer(
            text,
            reply_markup=admin_quests_keyboard(),
            parse_mode="HTML"
        )
    await callback.answer()


# Отклонить

@router.callback_query(F.data.startswith("quest_reject:"))
async def ask_reject_reason(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_owner(callback.from_user.id):
        return await callback.answer("No access.", show_alert=True)
    assignment_id = int(callback.data.split(":")[1])
    await state.set_state(RejectQuest.waiting_reason)
    await state.update_data(assignment_id=assignment_id)
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="\u23ed\ufe0f Без причины", callback_data=f"quest_reject_no_reason:{assignment_id}"))
    builder.row(InlineKeyboardButton(text="\u274c Отмена", callback_data="quest_submissions"))
    await _edit_or_reply(
        callback,
        "\u274c <b>Отклонение квеста</b>\n\nВведите причину отклонения (или нажмите «Без причины»):",
        reply_markup=builder.as_markup(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("quest_reject_no_reason:"))
async def reject_no_reason(callback: CallbackQuery, state: FSMContext, bot) -> None:
    if not _is_owner(callback.from_user.id):
        return await callback.answer("No access.", show_alert=True)
    assignment_id = int(callback.data.split(":")[1])
    await state.clear()
    await _do_reject(callback, bot, assignment_id, reason=None)


@router.message(RejectQuest.waiting_reason)
async def reject_with_reason(message: Message, state: FSMContext, bot) -> None:
    if not _is_owner(message.from_user.id):
        return
    data = await state.get_data()
    assignment_id = data["assignment_id"]
    reason = message.text.strip()
    await state.clear()

    class FakeCallback:
        def __init__(self, msg): self.message = msg
        async def answer(self, *a, **kw): pass

    await _do_reject(FakeCallback(message), bot, assignment_id, reason=reason)


async def _do_reject(callback, bot, assignment_id: int, reason) -> None:
    a = await queries.get_assignment_by_id(assignment_id)
    if not a:
        return await callback.answer("Назначение не найдено.", show_alert=True)
    await queries.reject_assignment(assignment_id, reviewed_by=config.owner_id, reason=reason)
    reason_text = f"\n\U0001f4ac Причина: {reason}" if reason else ""
    try:
        await bot.send_message(
            a["user_telegram_id"],
            f"\u274c <b>Квест не принят.</b>\n\n"
            f"Квест: <b>{a['title']}</b>{reason_text}",
            parse_mode="HTML",
        )
    except Exception:
        pass
    text = f"\u274c Квест отклонён. Пользователь уведомлён."
    if callback.message:
        try:
            if callback.message.photo or callback.message.video:
                await callback.message.edit_caption(
                    caption=text,
                    reply_markup=admin_quests_keyboard(),
                    parse_mode="HTML"
                )
            else:
                await callback.message.edit_text(
                    text,
                    reply_markup=admin_quests_keyboard(),
                    parse_mode="HTML"
                )
        except Exception:
            await callback.message.answer(
                text,
                reply_markup=admin_quests_keyboard(),
                parse_mode="HTML"
            )
    await callback.answer()


# Отмена формы

@router.callback_query(F.data == "cancel_admin_form")
async def cancel_quest_form(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    if _is_owner(callback.from_user.id):
        await _edit_or_reply(
            callback,
            "\U0001f4cb <b>Управление квестами</b>\n\nВыберите действие:",
            reply_markup=admin_quests_keyboard(),
        )
    await callback.answer()
