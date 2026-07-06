"""
Управление админ-валютами: рубли и звёзды (Admin).
Выдавать / снимать / устанавливать может только Owner.
"""

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from bot.config import config
from bot.database import queries
from bot.keyboards.admin import (
    manage_admin_currency_keyboard,
    admin_back_keyboard,
    cancel_admin_keyboard,
)
from bot.states.forms import ManageAdminCurrency
from bot.utils.logger import log_admin_action

router = Router()


# Метаданные валют: emoji, единственное/род. падеж, признак дробного значения
CURRENCY_META = {
    "rubles": {
        "emoji": "💰",
        "label_nom": "рубли",
        "label_acc": "рубли",
        "label_gen": "рублей",
        "unit": "₽",
        "is_float": True,
    },
    "stars": {
        "emoji": "🌟",
        "label_nom": "звёзды",
        "label_acc": "звёзды",
        "label_gen": "звёзд",
        "unit": "шт.",
        "is_float": False,
    },
}


def _is_owner(callback: CallbackQuery) -> bool:
    return callback.from_user.id == config.owner_id


def _is_owner_msg(message: Message) -> bool:
    return message.from_user.id == config.owner_id


def _fmt_amount(currency: str, amount: float) -> str:
    """Форматировать сумму в зависимости от валюты."""
    if CURRENCY_META[currency]["is_float"]:
        return f"{amount:g}"
    return str(int(amount))


def _fmt_balance(currency: str, user: dict) -> str:
    """Форматировать текущий баланс пользователя."""
    val = user.get(currency, 0) or 0
    return _fmt_amount(currency, val)


# Меню управления валютой из профиля пользователя

@router.callback_query(F.data.startswith("manage_rubles:") | F.data.startswith("manage_stars:"))
async def manage_admin_currency_from_profile(callback: CallbackQuery) -> None:
    if not _is_owner(callback):
        await callback.answer("⛔ Доступ запрещён.", show_alert=True)
        return

    parts = callback.data.split(":")
    currency = "rubles" if parts[0] == "manage_rubles" else "stars"
    telegram_id = int(parts[1])

    user = await queries.get_user_by_telegram_id(telegram_id)
    if not user:
        await callback.answer("Пользователь не найден.", show_alert=True)
        return

    meta = CURRENCY_META[currency]
    balance_str = _fmt_balance(currency, user)

    await callback.message.edit_text(
        f"{meta['emoji']} <b>Управление: {meta['label_nom']}</b>\n"
        f"👤 Пользователь: <b>{user['nickname']}</b>\n"
        f"{meta['emoji']} Текущий баланс: <b>{balance_str} {meta['unit']}</b>\n\n"
        f"Выберите действие:",
        reply_markup=manage_admin_currency_keyboard(telegram_id, currency),
        parse_mode="HTML"
    )
    await callback.answer()


# Инициализация операций (give / take / set)

@router.callback_query(
    F.data.startswith("give_rubles_to:")
    | F.data.startswith("take_rubles_from:")
    | F.data.startswith("give_stars_to:")
    | F.data.startswith("take_stars_from:")
)
async def give_take_admin_currency_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_owner(callback):
        await callback.answer("⛔ Доступ запрещён.", show_alert=True)
        return

    parts = callback.data.split(":")
    action = parts[0]
    telegram_id = int(parts[1])

    if "rubles" in action:
        currency = "rubles"
    else:
        currency = "stars"
    operation = "add" if action.startswith("give_") else "subtract"

    meta = CURRENCY_META[currency]
    op_emoji = "➕" if operation == "add" else "➖"
    op_text = "Выдача" if operation == "add" else "Снятие"

    await state.set_state(ManageAdminCurrency.waiting_amount)
    await state.update_data(
        currency_type=currency,
        operation=operation,
        target_telegram_id=telegram_id,
    )

    hint = "(можно дробное, например 100 или 50.5)" if meta["is_float"] else "(только целое число)"
    await callback.message.edit_text(
        f"{op_emoji} <b>{op_text}: {meta['label_nom']}</b>\n\n"
        f"Введите количество {meta['label_gen']} {hint}:",
        reply_markup=cancel_admin_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("set_rubles_for:") | F.data.startswith("set_stars_for:"))
async def set_admin_currency_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_owner(callback):
        await callback.answer("⛔ Доступ запрещён.", show_alert=True)
        return

    parts = callback.data.split(":")
    action = parts[0]
    telegram_id = int(parts[1])
    currency = "rubles" if "rubles" in action else "stars"

    meta = CURRENCY_META[currency]

    await state.set_state(ManageAdminCurrency.waiting_amount)
    await state.update_data(
        currency_type=currency,
        operation="set",
        target_telegram_id=telegram_id,
    )

    hint = "(можно дробное)" if meta["is_float"] else "(только целое число)"
    await callback.message.edit_text(
        f"🔄 <b>Установить баланс: {meta['label_nom']}</b>\n\n"
        f"Введите новое количество {meta['label_gen']} {hint}:",
        reply_markup=cancel_admin_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


# FSM: ввод количества → ввод причины → применение

@router.message(ManageAdminCurrency.waiting_amount)
async def admin_currency_get_amount(message: Message, state: FSMContext) -> None:
    if not _is_owner_msg(message) or not message.text:
        return

    data = await state.get_data()
    currency = data.get("currency_type")
    if currency not in CURRENCY_META:
        await state.clear()
        return

    meta = CURRENCY_META[currency]
    operation = data.get("operation", "add")
    raw = message.text.strip().replace(",", ".")

    try:
        if meta["is_float"]:
            amount = float(raw)
        else:
            amount = float(raw)
            if not amount.is_integer():
                raise ValueError
            amount = int(amount)
        # для "set" разрешаем 0, для add/subtract требуем > 0
        if operation == "set":
            if amount < 0:
                raise ValueError
        else:
            if amount <= 0:
                raise ValueError
    except ValueError:
        example = "5 или 100.5" if meta["is_float"] else "5"
        hint_zero = " или 0" if operation == "set" else ""
        await message.answer(
            f"⚠️ Введите положительное число{hint_zero} (например, {example}).",
            reply_markup=cancel_admin_keyboard()
        )
        return

    await state.update_data(amount=amount)
    await state.set_state(ManageAdminCurrency.waiting_reason)
    amount_str = _fmt_amount(currency, amount)
    await message.answer(
        f"{meta['emoji']} Количество: <b>{amount_str} {meta['unit']}</b>\n\n"
        f"Введите причину операции:",
        reply_markup=cancel_admin_keyboard(),
        parse_mode="HTML"
    )


@router.message(ManageAdminCurrency.waiting_reason)
async def admin_currency_get_reason(message: Message, state: FSMContext, bot: Bot) -> None:
    if not _is_owner_msg(message) or not message.text:
        await message.answer("⚠️ Введите причину операции.", reply_markup=cancel_admin_keyboard())
        return

    reason = message.text.strip()
    data = await state.get_data()
    await state.clear()

    currency = data["currency_type"]
    telegram_id = data["target_telegram_id"]
    amount = data["amount"]
    operation = data["operation"]

    user = await queries.get_user_by_telegram_id(telegram_id)
    if not user:
        await message.answer("❌ Пользователь не найден.", reply_markup=admin_back_keyboard())
        return

    await queries.update_user_balance(user["id"], currency, operation, amount)
    await queries.add_transaction(
        user_id=user["id"],
        currency_type=currency,
        operation=operation,
        amount=amount,
        reason=reason,
        performed_by=message.from_user.id,
    )

    updated = await queries.get_user_by_telegram_id(telegram_id)
    meta = CURRENCY_META[currency]

    if operation == "add":
        op_emoji, op_text, op_text_cap = "➕", "выдано", "Выдано"
    elif operation == "subtract":
        op_emoji, op_text, op_text_cap = "➖", "снято", "Снято"
    else:
        op_emoji, op_text, op_text_cap = "🔄", "установлено", "Установлено"

    amount_str = _fmt_amount(currency, amount)
    balance_str = _fmt_balance(currency, updated)

    log_admin_action(
        message.from_user.id,
        f"{currency.upper()}_{operation.upper()}",
        f"TG:{telegram_id} ({user['nickname']}): {amount_str} | {reason}"
    )

    await message.answer(
        f"✅ <b>Готово!</b>\n\n"
        f"👤 {user['nickname']}\n"
        f"{op_emoji} {meta['emoji']} {op_text}: <b>{amount_str} {meta['unit']}</b>\n"
        f"📊 Новый баланс: <b>{balance_str} {meta['unit']}</b>\n"
        f"📝 Причина: {reason}",
        reply_markup=admin_back_keyboard(),
        parse_mode="HTML"
    )

    try:
        notif_emoji = "✅" if operation == "add" else ("➖" if operation == "subtract" else "🔄")
        notif_text = (
            f"{notif_emoji} <b>Изменение баланса ({meta['label_nom']})</b>\n\n"
            f"{op_emoji} {meta['emoji']} {op_text_cap}: <b>{amount_str} {meta['unit']}</b>\n"
            f"📊 Новый баланс: <b>{balance_str} {meta['unit']}</b>\n"
            f"📝 Причина: {reason}"
        )
        await bot.send_message(telegram_id, notif_text, parse_mode="HTML")
    except Exception:
        pass
