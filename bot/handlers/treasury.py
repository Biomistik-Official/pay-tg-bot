"""
Казна клуба: просмотр, пожертвования и Owner-операции.
"""

import html
import secrets
from math import isfinite

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.config import config
from bot.database import queries
from bot.keyboards.treasury import (
    donation_confirm_keyboard,
    donation_ticket_keyboard,
    donation_type_keyboard,
    owner_confirm_keyboard,
    owner_currency_keyboard,
    owner_reason_keyboard,
    treasury_cancel_keyboard,
    treasury_history_keyboard,
    treasury_main_keyboard,
    treasury_manage_keyboard,
)
from bot.states.forms import TreasuryDonation, TreasuryOwnerOperation
from bot.utils.formatters import TICKET_NAMES, format_datetime
from bot.utils.logger import log_admin_action
from bot.utils.treasury import (
    DONATION_CURRENCIES,
    TREASURY_CURRENCIES,
    format_treasury_amount,
)

router = Router()

TICKET_CURRENCIES = [
    "tickets_platinum",
    "tickets_gold",
    "tickets_silver",
    "tickets_bronze",
    "tickets_support",
    "tickets_help",
]


def _is_owner(telegram_id: int) -> bool:
    return telegram_id == config.owner_id


def _parse_amount(raw: str, currency_type: str) -> float | int:
    normalized = raw.strip().replace(" ", "").replace(",", ".")
    amount = float(normalized)
    if not isfinite(amount) or amount <= 0:
        raise ValueError
    if TREASURY_CURRENCIES[currency_type]["integer"]:
        if not amount.is_integer():
            raise ValueError
        return int(amount)
    return amount


def _treasury_text(snapshot: dict) -> str:
    balances = snapshot["balances"]
    lines = [
        "🏦 <b>Казна клуба</b>",
        "",
        f"⭐ Баллы: <b>{balances.get('points', 0):g}</b>",
        "",
        "🎫 <b>Тикеты:</b>",
    ]
    tickets = []
    for currency_type in TICKET_CURRENCIES:
        amount = balances.get(currency_type, 0)
        if amount:
            key = currency_type.removeprefix("tickets_")
            emoji, name = TICKET_NAMES.get(key, ("🎫", "Тикет"))
            tickets.append(f"  {emoji} {name}: <b>{int(amount)}</b> шт.")
    lines.extend(tickets or ["  <i>нет тикетов</i>"])

    other_currencies = ["rubles", "stars", "unwarns", "unmutes"]
    other = [
        format_treasury_amount(currency_type, balances[currency_type])
        for currency_type in other_currencies
        if balances.get(currency_type, 0)
    ]
    if other:
        lines.extend(["", "💳 <b>Другие средства:</b>"])
        lines.extend(f"  {item}" for item in other)

    changed = format_datetime(snapshot["last_changed"]) if snapshot["last_changed"] else "операций ещё не было"
    lines.extend(["", "📅 <b>Последнее изменение:</b>", changed])
    return "\n".join(lines)


async def _show_treasury(callback: CallbackQuery, state: FSMContext | None = None) -> None:
    if state:
        await state.clear()
    user = await queries.get_user_by_telegram_id(callback.from_user.id)
    if not user:
        await callback.answer("Профиль не найден. Введите /start", show_alert=True)
        return
    snapshot = await queries.get_treasury_snapshot()
    await callback.message.edit_text(
        _treasury_text(snapshot),
        reply_markup=treasury_main_keyboard(_is_owner(callback.from_user.id)),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "treasury")
async def show_treasury(callback: CallbackQuery, state: FSMContext) -> None:
    await _show_treasury(callback, state)


@router.callback_query(F.data == "treasury_cancel")
async def cancel_treasury_form(callback: CallbackQuery, state: FSMContext) -> None:
    await _show_treasury(callback, state)


@router.callback_query(F.data == "treasury_donate")
async def start_donation(callback: CallbackQuery, state: FSMContext) -> None:
    if _is_owner(callback.from_user.id):
        await callback.answer("Для Owner доступно ручное пополнение.", show_alert=True)
        return
    await state.clear()
    await callback.message.edit_text(
        "❤️ <b>Пожертвование в казну</b>\n\nЧто вы хотите передать?",
        reply_markup=donation_type_keyboard(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "treasury_donate_tickets")
async def choose_donation_ticket(callback: CallbackQuery) -> None:
    if _is_owner(callback.from_user.id):
        return await callback.answer("Доступ запрещён.", show_alert=True)
    await callback.message.edit_text(
        "🎫 <b>Выберите тип тикета:</b>",
        reply_markup=donation_ticket_keyboard(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("treasury_donate_currency:"))
async def choose_donation_currency(callback: CallbackQuery, state: FSMContext) -> None:
    if _is_owner(callback.from_user.id):
        return await callback.answer("Доступ запрещён.", show_alert=True)
    currency_type = callback.data.split(":", 1)[1]
    if currency_type not in DONATION_CURRENCIES:
        return await callback.answer("Этот тип средств недоступен.", show_alert=True)

    user = await queries.get_user_by_telegram_id(callback.from_user.id)
    if not user:
        return await callback.answer("Профиль не найден.", show_alert=True)

    await state.set_state(TreasuryDonation.waiting_amount)
    await state.update_data(currency_type=currency_type)
    current = user.get(currency_type, 0) or 0
    meta = TREASURY_CURRENCIES[currency_type]
    hint = "целое число" if meta["integer"] else "число"
    await callback.message.edit_text(
        f"❤️ <b>Пожертвование в казну</b>\n\n"
        f"{meta['emoji']} Сколько вы хотите пожертвовать?\n"
        f"📊 Ваш баланс: <b>{current:g}</b>\n\n"
        f"Введите {hint} больше нуля:",
        reply_markup=treasury_cancel_keyboard(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(TreasuryDonation.waiting_amount)
async def receive_donation_amount(message: Message, state: FSMContext) -> None:
    if _is_owner(message.from_user.id) or not message.text:
        return
    data = await state.get_data()
    currency_type = data.get("currency_type")
    if currency_type not in DONATION_CURRENCIES:
        await state.clear()
        return
    try:
        amount = _parse_amount(message.text, currency_type)
    except (ValueError, OverflowError):
        await message.answer(
            "⚠️ Введите положительное "
            + ("целое число." if TREASURY_CURRENCIES[currency_type]["integer"] else "число."),
            reply_markup=treasury_cancel_keyboard(),
        )
        return

    user = await queries.get_user_by_telegram_id(message.from_user.id)
    if not user or float(user.get(currency_type, 0) or 0) < float(amount):
        await message.answer(
            "❌ Недостаточно средств для пожертвования.",
            reply_markup=treasury_cancel_keyboard(),
        )
        return

    await state.set_state(TreasuryDonation.confirm)
    await state.update_data(amount=amount, request_key=secrets.token_hex(16))
    formatted = format_treasury_amount(currency_type, amount)
    await message.answer(
        "❤️ <b>Пожертвование в казну</b>\n\n"
        f"➖ Будет списано: <b>{formatted}</b>\n"
        f"🏦 Будет добавлено в казну: <b>{formatted}</b>\n\n"
        "Подтвердить?",
        reply_markup=donation_confirm_keyboard(),
        parse_mode="HTML",
    )


@router.callback_query(TreasuryDonation.confirm, F.data == "treasury_donate_confirm")
async def confirm_donation(callback: CallbackQuery, state: FSMContext) -> None:
    if _is_owner(callback.from_user.id):
        return await callback.answer("Доступ запрещён.", show_alert=True)
    data = await state.get_data()
    try:
        result = await queries.donate_to_treasury(
            telegram_id=callback.from_user.id,
            currency_type=data["currency_type"],
            amount=data["amount"],
            request_key=data["request_key"],
        )
    except queries.TreasuryInsufficientFundsError:
        await state.clear()
        await callback.answer("❌ Недостаточно средств для пожертвования.", show_alert=True)
        await callback.message.edit_text(
            "❌ <b>Недостаточно средств для пожертвования.</b>",
            reply_markup=treasury_main_keyboard(False),
            parse_mode="HTML",
        )
        return
    except (queries.TreasuryUserNotFoundError, ValueError):
        await state.clear()
        return await callback.answer("❌ Не удалось выполнить пожертвование.", show_alert=True)

    await state.clear()
    formatted = format_treasury_amount(result["currency_type"], result["amount"])
    await callback.message.edit_text(
        "❤️ <b>Спасибо за поддержку клуба!</b>\n\n"
        "Вы пожертвовали:\n"
        f"<b>{formatted}</b>\n\n"
        "Средства успешно добавлены в казну.",
        reply_markup=treasury_main_keyboard(False),
        parse_mode="HTML",
    )
    await callback.answer("✅ Пожертвование принято!")


@router.callback_query(F.data.in_({"treasury_owner_add", "treasury_owner_expense"}))
async def start_owner_operation(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_owner(callback.from_user.id):
        return await callback.answer("⛔ Доступ запрещён.", show_alert=True)
    await state.clear()
    operation_type = "manual_deposit" if callback.data == "treasury_owner_add" else "expense"
    title = "➕ Пополнение казны" if operation_type == "manual_deposit" else "➖ Расход из казны"
    await callback.message.edit_text(
        f"{title}\n\nВыбери тип средств:",
        reply_markup=owner_currency_keyboard(operation_type),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("treasury_owner_currency:"))
async def choose_owner_currency(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_owner(callback.from_user.id):
        return await callback.answer("⛔ Доступ запрещён.", show_alert=True)
    _, operation_type, currency_type = callback.data.split(":", 2)
    if operation_type not in {"manual_deposit", "expense"} or currency_type not in TREASURY_CURRENCIES:
        return await callback.answer("Неверная операция.", show_alert=True)

    await state.set_state(TreasuryOwnerOperation.waiting_amount)
    await state.update_data(operation_type=operation_type, currency_type=currency_type)
    meta = TREASURY_CURRENCIES[currency_type]
    action = "добавить" if operation_type == "manual_deposit" else "списать"
    hint = "целое число" if meta["integer"] else "число"
    await callback.message.edit_text(
        f"{meta['emoji']} <b>{meta['name']}</b>\n\n"
        f"Какое количество нужно {action}?\n"
        f"Введи {hint} больше нуля:",
        reply_markup=treasury_cancel_keyboard(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(TreasuryOwnerOperation.waiting_amount)
async def receive_owner_amount(message: Message, state: FSMContext) -> None:
    if not _is_owner(message.from_user.id) or not message.text:
        return
    data = await state.get_data()
    currency_type = data.get("currency_type")
    if currency_type not in TREASURY_CURRENCIES:
        await state.clear()
        return
    try:
        amount = _parse_amount(message.text, currency_type)
    except (ValueError, OverflowError):
        await message.answer(
            "⚠️ Введи положительное "
            + ("целое число." if TREASURY_CURRENCIES[currency_type]["integer"] else "число."),
            reply_markup=treasury_cancel_keyboard(),
        )
        return

    operation_type = data["operation_type"]
    await state.update_data(amount=amount)
    await state.set_state(TreasuryOwnerOperation.waiting_reason)
    prompt = "Введи причину списания:" if operation_type == "expense" else "Введи комментарий или нажми «Без комментария»:"
    await message.answer(
        f"{format_treasury_amount(currency_type, amount)}\n\n{prompt}",
        reply_markup=owner_reason_keyboard(operation_type == "manual_deposit"),
        parse_mode="HTML",
    )


async def _show_owner_confirmation(target, state: FSMContext, reason: str) -> None:
    data = await state.get_data()
    await state.set_state(TreasuryOwnerOperation.confirm)
    await state.update_data(reason=reason, request_key=secrets.token_hex(16))
    operation_type = data["operation_type"]
    title = "➕ <b>Пополнение казны</b>" if operation_type == "manual_deposit" else "➖ <b>Расход из казны</b>"
    reason_text = html.escape(reason) if reason else "без комментария"
    text = (
        f"{title}\n\n"
        f"Сумма: <b>{format_treasury_amount(data['currency_type'], data['amount'])}</b>\n"
        f"📝 Причина: {reason_text}\n\n"
        "Подтвердить?"
    )
    if isinstance(target, CallbackQuery):
        await target.message.edit_text(text, reply_markup=owner_confirm_keyboard(), parse_mode="HTML")
        await target.answer()
    else:
        await target.answer(text, reply_markup=owner_confirm_keyboard(), parse_mode="HTML")


@router.message(TreasuryOwnerOperation.waiting_reason)
async def receive_owner_reason(message: Message, state: FSMContext) -> None:
    if not _is_owner(message.from_user.id) or not message.text:
        return
    reason = message.text.strip()
    data = await state.get_data()
    if data.get("operation_type") == "expense" and not reason:
        await message.answer("⚠️ Причина списания обязательна.")
        return
    await _show_owner_confirmation(message, state, reason[:500])


@router.callback_query(TreasuryOwnerOperation.waiting_reason, F.data == "treasury_reason_skip")
async def skip_owner_reason(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_owner(callback.from_user.id):
        return await callback.answer("⛔ Доступ запрещён.", show_alert=True)
    data = await state.get_data()
    if data.get("operation_type") != "manual_deposit":
        return await callback.answer("Причина списания обязательна.", show_alert=True)
    await _show_owner_confirmation(callback, state, "")


@router.callback_query(TreasuryOwnerOperation.confirm, F.data == "treasury_owner_confirm")
async def confirm_owner_operation(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_owner(callback.from_user.id):
        return await callback.answer("⛔ Доступ запрещён.", show_alert=True)
    data = await state.get_data()
    try:
        result = await queries.adjust_treasury_balance(
            operation_type=data["operation_type"],
            currency_type=data["currency_type"],
            amount=data["amount"],
            initiated_by_telegram_id=callback.from_user.id,
            reason=data["reason"],
            request_key=data["request_key"],
        )
    except queries.TreasuryInsufficientFundsError:
        await state.clear()
        await callback.answer("❌ В казне недостаточно средств.", show_alert=True)
        await callback.message.edit_text(
            "❌ <b>В казне недостаточно средств.</b>",
            reply_markup=treasury_main_keyboard(True),
            parse_mode="HTML",
        )
        return
    except ValueError as error:
        await state.clear()
        return await callback.answer(f"❌ {error}", show_alert=True)

    await state.clear()
    action = "пополнена" if result["operation_type"] == "manual_deposit" else "списано"
    formatted = format_treasury_amount(result["currency_type"], result["amount"])
    log_admin_action(
        callback.from_user.id,
        "TREASURY_DEPOSIT" if result["operation_type"] == "manual_deposit" else "TREASURY_EXPENSE",
        f"{result['currency_type']} {result['amount']:g} | {data['reason'] or 'без комментария'}",
    )
    await callback.message.edit_text(
        f"✅ <b>Казна {action}</b>\n\n"
        f"Сумма: <b>{formatted}</b>\n"
        f"🏦 Баланс после операции: "
        f"<b>{format_treasury_amount(result['currency_type'], result['balance_after'])}</b>",
        reply_markup=treasury_main_keyboard(True),
        parse_mode="HTML",
    )
    await callback.answer("✅ Операция выполнена.")


@router.callback_query(F.data.startswith("treasury_history:"))
async def show_treasury_history(callback: CallbackQuery) -> None:
    if not _is_owner(callback.from_user.id):
        return await callback.answer("⛔ История казны доступна только Owner.", show_alert=True)
    try:
        offset = max(0, int(callback.data.split(":", 1)[1]))
    except ValueError:
        offset = 0
    page_size = 8
    rows = await queries.get_treasury_history(page_size, offset)
    total = await queries.count_treasury_history()
    lines = ["📜 <b>История казны</b>"]
    if not rows:
        lines.extend(["", "Операций пока нет."])
    for row in rows:
        if row["operation_type"] == "donation":
            icon, title, sign = "❤️", "Пожертвование", "+"
        elif row["operation_type"] == "manual_deposit":
            icon, title, sign = "➕", "Пополнение Owner", "+"
        else:
            icon, title, sign = "➖", "Расход", "−"
        amount = format_treasury_amount(row["currency_type"], row["amount"])
        related = ""
        if row.get("related_user_nickname"):
            related = f"\n👤 Пользователь: {html.escape(row['related_user_nickname'])}"
        initiator = row.get("initiator_nickname") or str(row["initiated_by_telegram_id"])
        reason = f"\n📝 {html.escape(row['reason'])}" if row.get("reason") else ""
        lines.append(
            f"\n{icon} <b>{title}</b>\n"
            f"{sign} {amount}\n"
            f"📊 {row['balance_before']:g} → {row['balance_after']:g}"
            f"{related}\n👑 Инициатор: {html.escape(initiator)}"
            f"{reason}\n📅 {format_datetime(row['created_at'])}"
        )
    await callback.message.edit_text(
        "\n".join(lines),
        reply_markup=treasury_history_keyboard(offset, total, page_size),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "treasury_manage")
async def show_treasury_management(callback: CallbackQuery) -> None:
    if not _is_owner(callback.from_user.id):
        return await callback.answer("⛔ Доступ запрещён.", show_alert=True)
    await callback.message.edit_text(
        "⚙️ <b>Управление казной</b>\n\n"
        "❤️ Пожертвования: баллы и все типы тикетов.\n"
        "👑 Ручные операции: все поддерживаемые средства.\n"
        "🔐 Баланс казны не может уйти в минус.\n"
        "🧩 Все операции атомарны и записываются в историю.",
        reply_markup=treasury_manage_keyboard(),
        parse_mode="HTML",
    )
    await callback.answer()
