"""
Обработчик заявок пользователя (запрос тикетов/баллов).

Тикеты теперь — именные билеты (Платиновый, Золотой, Серебряный, Бронзовый, Вспомогательный).
Пользователь выбирает тип тикета кнопкой, затем вводит причину.

Баллы — числовые, вводятся вручную.
"""

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from bot.config import config
from bot.database import queries
from bot.keyboards.user import (
    tickets_menu_keyboard,
    points_menu_keyboard,
    ticket_type_keyboard,
    cancel_keyboard,
    TICKET_TYPES,
)
from bot.keyboards.admin import request_action_keyboard
from bot.states.forms import RequestTickets, RequestPoints
from bot.utils.formatters import format_request_for_owner
from bot.utils.logger import logger

router = Router()

# Словарь типов тикетов: ключ → (emoji, название, стоимость в баллах)
TICKET_INFO = {key: (emoji, name, value) for key, emoji, name, value in TICKET_TYPES}


async def _check_daily_limit(user: dict, callback: CallbackQuery) -> bool:
    """Проверить лимит заявок за день. Возвращает True если лимит не превышен."""
    count = await queries.count_user_requests_today(user["id"])
    if count >= config.daily_request_limit:
        await callback.answer(
            f"⚠️ Вы достигли лимита заявок на сегодня ({config.daily_request_limit} шт.).\n"
            "Попробуйте завтра.",
            show_alert=True
        )
        return False
    return True


# ──────────────────────────────────────────────
# Меню Тикеты / Баллы
# ──────────────────────────────────────────────

@router.callback_query(F.data == "tickets_menu")
async def tickets_menu(callback: CallbackQuery) -> None:
    """Раздел Тикеты."""
    user = await queries.get_user_by_telegram_id(callback.from_user.id)
    if not user:
        await callback.answer("Профиль не найден. Введите /start", show_alert=True)
        return
    if user.get("is_blocked"):
        await callback.answer("🚫 Ваш аккаунт заблокирован.", show_alert=True)
        return

    platinum = user.get('tickets_platinum', 0)
    gold = user.get('tickets_gold', 0)
    silver = user.get('tickets_silver', 0)
    bronze = user.get('tickets_bronze', 0)
    support = user.get('tickets_support', 0)
    help_t = user.get('tickets_help', 0)

    tickets_list = []
    if platinum > 0: tickets_list.append(f"  💎 Платиновый: <b>{platinum}</b> шт.")
    if gold > 0:     tickets_list.append(f"  🥇 Золотой: <b>{gold}</b> шт.")
    if silver > 0:   tickets_list.append(f"  🥈 Серебряный: <b>{silver}</b> шт.")
    if bronze > 0:   tickets_list.append(f"  🥉 Бронзовый: <b>{bronze}</b> шт.")
    if support > 0:  tickets_list.append(f"  🎁 Вспомогательный: <b>{support}</b> шт.")
    if help_t > 0:   tickets_list.append(f"  💪 Хелп тикет: <b>{help_t}</b> шт.")
    
    tickets_text = "\n" + "\n".join(tickets_list) if tickets_list else "  <i>нет тикетов</i>"

    info_lines_list = []
    for key, emoji, name, value in TICKET_TYPES:
        if key == "help":
            info_lines_list.append(f"  {emoji} <b>{name}</b> — только по запросу")
        else:
            info_lines_list.append(f"  {emoji} <b>{name}</b> — {value:g} балл{'а' if value < 2 or 2 <= value < 5 else 'ов'}")
    info_lines = "\n".join(info_lines_list)

    await callback.message.edit_text(
        f"🎫 <b>Тикеты</b>\n\n"
        f"У вас в наличии:{tickets_text}\n\n"
        f"<b>Цена тикетов в баллах:</b>\n{info_lines}\n\n"
        f"Выберите действие:",
        reply_markup=tickets_menu_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "points_menu")
async def points_menu(callback: CallbackQuery) -> None:
    """Раздел Баллы."""
    user = await queries.get_user_by_telegram_id(callback.from_user.id)
    if not user:
        await callback.answer("Профиль не найден. Введите /start", show_alert=True)
        return
    if user.get("is_blocked"):
        await callback.answer("🚫 Ваш аккаунт заблокирован.", show_alert=True)
        return

    points_str = f"{user['points']:g}"

    await callback.message.edit_text(
        f"⭐ <b>Баллы</b>\n\n"
        f"У вас баллов: <b>{points_str}</b>\n\n"
        f"Выберите действие:",
        reply_markup=points_menu_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


# ──────────────────────────────────────────────
# Запрос тикетов — шаг 1: выбор типа кнопкой
# ──────────────────────────────────────────────

@router.callback_query(F.data == "request_tickets")
async def request_tickets_start(callback: CallbackQuery, state: FSMContext) -> None:
    """Начать процесс запроса тикета — показать список типов."""
    user = await queries.get_user_by_telegram_id(callback.from_user.id)
    if not user:
        await callback.answer("Профиль не найден.", show_alert=True)
        return

    if not await _check_daily_limit(user, callback):
        return

    await state.set_state(RequestTickets.waiting_ticket_type)
    await callback.message.edit_text(
        "🎫 <b>Запрос тикета</b>\n\n"
        "Выберите <b>тип тикета</b>, который хотите запросить:",
        reply_markup=ticket_type_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


# ──────────────────────────────────────────────
# Запрос тикетов — шаг 2: ввод причины
# ──────────────────────────────────────────────

@router.callback_query(RequestTickets.waiting_ticket_type, F.data.startswith("ticket_type:"))
async def request_tickets_type_chosen(callback: CallbackQuery, state: FSMContext) -> None:
    """Пользователь выбрал тип тикета — просим причину."""
    ticket_key = callback.data.split(":")[1]

    if ticket_key not in TICKET_INFO:
        await callback.answer("Неизвестный тип тикета.", show_alert=True)
        return

    emoji, name, value = TICKET_INFO[ticket_key]
    value_str = f"{value:g}"

    await state.update_data(ticket_key=ticket_key, ticket_name=name, ticket_emoji=emoji, ticket_value=value)
    await state.set_state(RequestTickets.waiting_reason)

    await callback.message.edit_text(
        f"🎫 <b>Запрос: {emoji} {name} тикет</b> ({value_str} балл{'а' if value < 2 or 2 <= value < 5 else 'ов'})\n\n"
        "📝 Теперь напишите <b>причину</b> получения тикета:",
        reply_markup=cancel_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


# ──────────────────────────────────────────────
# Запрос тикетов — шаг 3: отправка заявки
# ──────────────────────────────────────────────

@router.message(RequestTickets.waiting_reason)
async def request_tickets_reason(message: Message, state: FSMContext, bot: Bot) -> None:
    """Обработать причину и отправить заявку на тикет."""
    if not message.text:
        await message.answer(
            "⚠️ Пожалуйста, напишите текстовую причину получения тикета.",
            reply_markup=cancel_keyboard()
        )
        return

    reason = message.text.strip()
    if len(reason) < 3:
        await message.answer(
            "⚠️ Причина слишком короткая. Минимум 3 символа.",
            reply_markup=cancel_keyboard()
        )
        return

    data = await state.get_data()
    ticket_key   = data["ticket_key"]
    ticket_name  = data["ticket_name"]
    ticket_emoji = data["ticket_emoji"]
    ticket_value = data["ticket_value"]

    user = await queries.get_user_by_telegram_id(message.from_user.id)

    # Создаём заявку в БД: amount = 1 тикет, reason содержит тип тикета + причину
    full_reason = f"[{ticket_emoji} {ticket_name} тикет] {reason}"
    request_id = await queries.create_request(
        user_id=user["id"],
        currency_type=f"tickets_{ticket_key}",
        amount=1,
        reason=full_reason
    )
    req = await queries.get_request_by_id(request_id)

    await state.clear()

    value_str = f"{ticket_value:g}"

    # Уведомляем пользователя
    await message.answer(
        f"✅ <b>Заявка на тикет отправлена!</b>\n\n"
        f"{ticket_emoji} <b>{ticket_name} тикет</b> ({value_str} балл{'а' if ticket_value < 2 or 2 <= ticket_value < 5 else 'ов'})\n"
        f"📝 Причина: {reason}\n\n"
        "Ожидайте решения владельца.",
        parse_mode="HTML"
    )

    # Уведомляем Owner
    owner_text = format_request_for_owner(req, user)
    try:
        await bot.send_message(
            config.owner_id,
            owner_text,
            reply_markup=request_action_keyboard(request_id),
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Не удалось отправить уведомление Owner: {e}")

    logger.info(f"Заявка #{request_id} на {ticket_name} тикет от {user['nickname']} (TG:{user['telegram_id']})")


# ──────────────────────────────────────────────
# Запрос баллов — шаг 1: ввод количества
# ──────────────────────────────────────────────

@router.callback_query(F.data == "request_points")
async def request_points_start(callback: CallbackQuery, state: FSMContext) -> None:
    """Начать процесс запроса баллов."""
    user = await queries.get_user_by_telegram_id(callback.from_user.id)
    if not user:
        await callback.answer("Профиль не найден.", show_alert=True)
        return

    if not await _check_daily_limit(user, callback):
        return

    await state.set_state(RequestPoints.waiting_amount)
    await callback.message.edit_text(
        "⭐ <b>Запрос баллов</b>\n\n"
        "Введите количество баллов, которое хотите запросить:\n\n"
        "<i>Можно использовать дробные числа, например: 5 или 2.5</i>",
        reply_markup=cancel_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(RequestPoints.waiting_amount)
async def request_points_amount(message: Message, state: FSMContext) -> None:
    """Обработать количество баллов."""
    if not message.text:
        await message.answer(
            "⚠️ Пожалуйста, введите количество числом.",
            reply_markup=cancel_keyboard()
        )
        return

    try:
        amount = float(message.text.strip().replace(",", "."))
        if amount <= 0:
            raise ValueError
        if amount.is_integer():
            amount = int(amount)
    except ValueError:
        await message.answer(
            "⚠️ Введите корректное положительное число (например, 5 или 2.5).",
            reply_markup=cancel_keyboard()
        )
        return

    await state.update_data(amount=amount)
    await state.set_state(RequestPoints.waiting_reason)
    amount_str = f"{amount:g}"
    await message.answer(
        f"⭐ Количество: <b>{amount_str}</b>\n\n"
        "📝 Теперь напишите причину получения баллов:",
        reply_markup=cancel_keyboard(),
        parse_mode="HTML"
    )


@router.message(RequestPoints.waiting_reason)
async def request_points_reason(message: Message, state: FSMContext, bot: Bot) -> None:
    """Обработать причину и отправить заявку на баллы."""
    if not message.text:
        await message.answer(
            "⚠️ Пожалуйста, напишите текстовую причину получения баллов.",
            reply_markup=cancel_keyboard()
        )
        return

    reason = message.text.strip()
    if len(reason) < 3:
        await message.answer(
            "⚠️ Причина слишком короткая. Минимум 3 символа.",
            reply_markup=cancel_keyboard()
        )
        return

    data = await state.get_data()
    amount = data["amount"]

    user = await queries.get_user_by_telegram_id(message.from_user.id)

    request_id = await queries.create_request(
        user_id=user["id"],
        currency_type="points",
        amount=amount,
        reason=reason
    )
    req = await queries.get_request_by_id(request_id)

    await state.clear()

    amount_str = f"{amount:g}"

    # Уведомляем пользователя
    await message.answer(
        f"✅ <b>Заявка на баллы отправлена!</b>\n\n"
        f"⭐ Количество: <b>{amount_str}</b>\n"
        f"📝 Причина: {reason}\n\n"
        "Ожидайте решения владельца.",
        parse_mode="HTML"
    )

    # Уведомляем Owner
    owner_text = format_request_for_owner(req, user)
    try:
        await bot.send_message(
            config.owner_id,
            owner_text,
            reply_markup=request_action_keyboard(request_id),
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Не удалось отправить уведомление Owner: {e}")

    logger.info(f"Заявка #{request_id} на баллы от {user['nickname']} (TG:{user['telegram_id']}): {amount_str}")
