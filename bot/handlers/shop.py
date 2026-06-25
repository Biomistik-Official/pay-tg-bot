"""
Обработчики Магазина для пользователей.
"""

import json
from datetime import datetime

from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext

from bot.config import config
from bot.database import queries
from bot.keyboards.user import (
    shop_main_keyboard,
    shop_tickets_keyboard,
    confirm_purchase_keyboard,
    shop_points_keyboard,
    shop_exchange_ticket_keyboard,
    confirm_exchange_keyboard,
    confirm_withdraw_keyboard,
    contact_owner_keyboard,
    back_to_shop_keyboard,
    TICKET_TYPES,
    TICKET_NAMES_SHORT,
    ROULETTE_ITEMS,
    cancel_keyboard,
)
from bot.states.forms import ShopExchange, ShopWithdraw
from bot.utils.logger import logger

router = Router()

OWNER_ID = config.owner_id


def _ticket_name(key: str) -> tuple:
    """Получить (emoji, название) тикета по ключу."""
    return TICKET_NAMES_SHORT.get(key, ("🎫", key.capitalize()))


# ──────────────────────────────────────────────
# Главное меню магазина
# ──────────────────────────────────────────────

@router.callback_query(F.data == "shop_main")
async def shop_main(callback: CallbackQuery, state: FSMContext) -> None:
    """Главное меню магазина."""
    await state.clear()
    user = await queries.get_user_by_telegram_id(callback.from_user.id)
    if not user or user.get("is_blocked"):
        await callback.answer("🚫 Доступ запрещён.", show_alert=True)
        return

    await callback.message.edit_text(
        "🛒 <b>Магазин VGS Money</b>\n\n"
        "Выберите раздел:",
        reply_markup=shop_main_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


# ──────────────────────────────────────────────
# Магазин за тикеты
# ──────────────────────────────────────────────

@router.callback_query(F.data == "shop_tickets")
async def shop_tickets_menu(callback: CallbackQuery) -> None:
    """Список рулеток за тикеты."""
    user = await queries.get_user_by_telegram_id(callback.from_user.id)
    if not user or user.get("is_blocked"):
        await callback.answer("🚫 Доступ запрещён.", show_alert=True)
        return

    settings = await queries.get_shop_settings()
    pt = user.get("tickets_platinum", 0)
    gt = user.get("tickets_gold", 0)
    st = user.get("tickets_silver", 0)
    bt = user.get("tickets_bronze", 0)
    sut = user.get("tickets_support", 0)
    ht = user.get("tickets_help", 0)

    await callback.message.edit_text(
        "🎫 <b>Магазин за тикеты</b>\n\n"
        "💎 Платиновых: <b>{}</b>\n"
        "🥇 Золотых: <b>{}</b>\n"
        "🥈 Серебряных: <b>{}</b>\n"
        "🥉 Бронзовых: <b>{}</b>\n"
        "🎁 Вспомогательных: <b>{}</b>\n"
        "💪 Хелп тикетов: <b>{}</b>\n\n"
        "Выберите рулетку для покупки:".format(pt, gt, st, bt, sut, ht),
        reply_markup=shop_tickets_keyboard(settings),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "shop_unavailable")
async def shop_unavailable(callback: CallbackQuery) -> None:
    """Товар недоступен."""
    await callback.answer("🚫 Этот товар временно недоступен.", show_alert=True)


@router.callback_query(F.data.startswith("shop_buy:"))
async def shop_buy_item(callback: CallbackQuery) -> None:
    """Показать детали товара и запросить подтверждение."""
    item_key = callback.data.split(":")[1]
    user = await queries.get_user_by_telegram_id(callback.from_user.id)
    if not user or user.get("is_blocked"):
        await callback.answer("🚫 Доступ запрещён.", show_alert=True)
        return

    settings = await queries.get_shop_settings()
    active = settings.get(f"item_{item_key}_active", "1") == "1"
    if not active:
        await callback.answer("🚫 Этот товар недоступен.", show_alert=True)
        return

    roulette = next((r for r in ROULETTE_ITEMS if r[0] == item_key), None)
    if not roulette:
        await callback.answer("❌ Товар не найден.", show_alert=True)
        return

    _, emoji, name, ticket_type = roulette
    ticket_key = ticket_type.replace("tickets_", "")
    t_emoji, t_name = _ticket_name(ticket_key)
    cost = int(float(settings.get(f"roulette_cost_{item_key}", "1")))
    user_balance = user.get(ticket_type, 0)

    balance_line = (
        f"✅ Ваш баланс: <b>{user_balance}</b> {t_name} тикет(ов)"
        if user_balance >= cost
        else f"❌ Недостаточно тикетов (у вас: <b>{user_balance}</b>)"
    )

    await callback.message.edit_text(
        f"🎁 <b>Покупка товара</b>\n\n"
        f"📦 Название: <b>{emoji} {name}</b>\n"
        f"🎫 Стоимость: <b>{cost} {t_emoji} {t_name} тикет</b>\n\n"
        f"{balance_line}\n\n"
        f"Вы действительно хотите совершить покупку?",
        reply_markup=confirm_purchase_keyboard(item_key),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("shop_confirm:"))
async def shop_confirm_buy(callback: CallbackQuery, bot: Bot) -> None:
    """Подтверждение и выполнение покупки рулетки."""
    item_key = callback.data.split(":")[1]
    user = await queries.get_user_by_telegram_id(callback.from_user.id)
    if not user or user.get("is_blocked"):
        await callback.answer("🚫 Доступ запрещён.", show_alert=True)
        return

    settings = await queries.get_shop_settings()
    active = settings.get(f"item_{item_key}_active", "1") == "1"
    if not active:
        await callback.answer("🚫 Товар временно недоступен.", show_alert=True)
        return

    roulette = next((r for r in ROULETTE_ITEMS if r[0] == item_key), None)
    if not roulette:
        await callback.answer("❌ Товар не найден.", show_alert=True)
        return

    _, emoji, name, ticket_type = roulette
    ticket_key = ticket_type.replace("tickets_", "")
    t_emoji, t_name = _ticket_name(ticket_key)
    cost = int(float(settings.get(f"roulette_cost_{item_key}", "1")))
    user_balance = user.get(ticket_type, 0)

    if user_balance < cost:
        await callback.answer(
            f"❌ Недостаточно тикетов! Нужно: {cost}, у вас: {user_balance}",
            show_alert=True
        )
        return

    # Списываем тикеты
    await queries.update_user_balance(user["id"], ticket_type, "subtract", cost)

    # Записываем транзакцию
    await queries.add_transaction(
        user_id=user["id"],
        currency_type=ticket_type,
        operation="subtract",
        amount=cost,
        reason=f"Покупка в магазине: {emoji} {name}",
        performed_by=callback.from_user.id
    )

    # Создаём заявку в To-Do
    details = json.dumps({
        "type": "roulette",
        "item_key": item_key,
        "item_name": name,
        "item_emoji": emoji,
        "ticket_type": ticket_type,
        "ticket_name": f"{t_emoji} {t_name}",
        "cost": cost,
        "user_nickname": user["nickname"],
        "user_telegram_id": user["telegram_id"],
    }, ensure_ascii=False)
    order_id = await queries.create_shop_order(user["id"], "roulette", details)

    # Уведомление Owner
    date_str = datetime.now().strftime("%d.%m.%Y")
    try:
        await bot.send_message(
            OWNER_ID,
            f"🔔 <b>Новая покупка в магазине</b>\n\n"
            f"👤 Пользователь: <b>{user['nickname']}</b>\n"
            f"🆔 ID: <code>{user['telegram_id']}</code>\n"
            f"📦 Товар: <b>{emoji} {name}</b>\n"
            f"🎫 Стоимость: <b>{cost} {t_emoji} {t_name} тикет</b>\n"
            f"📋 Заявка #<b>{order_id}</b>\n"
            f"📅 Дата: {date_str}",
            parse_mode="HTML"
        )
    except Exception as e:
        logger.warning(f"Не удалось отправить уведомление owner: {e}")

    new_balance = user_balance - cost
    owner = await queries.get_user_by_telegram_id(OWNER_ID)
    owner_username = owner.get("username") if owner else None

    await callback.message.edit_text(
        f"✅ <b>Покупка успешно оформлена!</b>\n\n"
        f"📦 {emoji} <b>{name}</b>\n"
        f"🎫 Списано: <b>{cost} {t_emoji} {t_name} тикет</b>\n"
        f"💼 Остаток: <b>{new_balance}</b> {t_name} тикет(ов)\n\n"
        f"🎟️ Ваш билет зарезервирован.\n"
        f"Для получения награды свяжитесь с владельцем.",
        reply_markup=contact_owner_keyboard(OWNER_ID, owner_username),
        parse_mode="HTML"
    )
    await callback.answer("✅ Покупка оформлена!")
    logger.info(f"Shop purchase: {user['nickname']} купил {name} за {cost} {t_name}")


# ──────────────────────────────────────────────
# Магазин за баллы
# ──────────────────────────────────────────────

@router.callback_query(F.data == "shop_points")
async def shop_points_menu(callback: CallbackQuery, state: FSMContext) -> None:
    """Меню магазина за баллы."""
    await state.clear()
    user = await queries.get_user_by_telegram_id(callback.from_user.id)
    if not user or user.get("is_blocked"):
        await callback.answer("🚫 Доступ запрещён.", show_alert=True)
        return

    await callback.message.edit_text(
        f"⭐ <b>Магазин за баллы</b>\n\n"
        f"💼 Ваш баланс: <b>{user['points']:g}</b> баллов\n\n"
        f"Выберите раздел:",
        reply_markup=shop_points_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


# ──────────────────────────────────────────────
# Обмен баллов на тикеты
# ──────────────────────────────────────────────

@router.callback_query(F.data == "shop_exchange")
async def shop_exchange_menu(callback: CallbackQuery, state: FSMContext) -> None:
    """Меню обмена баллов на тикеты."""
    await state.clear()
    user = await queries.get_user_by_telegram_id(callback.from_user.id)
    if not user or user.get("is_blocked"):
        await callback.answer("🚫 Доступ запрещён.", show_alert=True)
        return

    settings = await queries.get_shop_settings()
    prices_text = "\n".join([
        f"  💎 Платиновый — {float(settings.get('ticket_price_platinum', '10')):g} б.",
        f"  🥇 Золотой — {float(settings.get('ticket_price_gold', '5')):g} б.",
        f"  🥈 Серебряный — {float(settings.get('ticket_price_silver', '2.5')):g} б.",
        f"  🥉 Бронзовый — {float(settings.get('ticket_price_bronze', '1.3')):g} б.",
        f"  🎁 Вспомогательный — {float(settings.get('ticket_price_support', '2.5')):g} б.",
        f"  💪 Хелп тикет — только по запросу",
    ])

    await callback.message.edit_text(
        f"🎫 <b>Обмен баллов на тикеты</b>\n\n"
        f"💼 Ваш баланс: <b>{user['points']:g}</b> баллов\n\n"
        f"<b>Цены тикетов:</b>\n{prices_text}\n\n"
        f"Выберите тип тикета:",
        reply_markup=shop_exchange_ticket_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("shop_exch_type:"))
async def shop_exchange_type(callback: CallbackQuery, state: FSMContext) -> None:
    """Выбор типа тикета → ввод количества тикетов для получения."""
    ticket_key = callback.data.split(":")[1]
    user = await queries.get_user_by_telegram_id(callback.from_user.id)
    if not user or user.get("is_blocked"):
        await callback.answer("🚫 Доступ запрещён.", show_alert=True)
        return

    settings = await queries.get_shop_settings()
    price_per_ticket = float(settings.get(f"ticket_price_{ticket_key}", "0"))
    if price_per_ticket <= 0:
        await callback.answer("❌ Этот тикет недоступен для обмена.", show_alert=True)
        return

    t_emoji, t_name = _ticket_name(ticket_key)

    await state.set_state(ShopExchange.waiting_amount)
    await state.update_data(
        ticket_key=ticket_key,
        price_per_ticket=price_per_ticket,
        t_emoji=t_emoji,
        t_name=t_name,
    )

    await callback.message.edit_text(
        f"🎫 <b>Обмен баллов на {t_emoji} {t_name} тикеты</b>\n\n"
        f"💰 Цена: <b>{price_per_ticket:g} балл</b> за 1 тикет\n"
        f"💼 Ваш баланс: <b>{user['points']:g}</b> баллов\n\n"
        f"Введите количество тикетов, которое хотите получить:",
        reply_markup=cancel_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(ShopExchange.waiting_amount)
async def shop_exchange_amount(message: Message, state: FSMContext) -> None:
    """Обработка введённого количества тикетов для обмена."""
    try:
        amount = int(message.text.strip())
        if amount <= 0:
            raise ValueError
    except ValueError:
        await message.answer(
            "⚠️ Введите положительное целое число.",
            reply_markup=cancel_keyboard()
        )
        return

    data = await state.get_data()
    ticket_key = data["ticket_key"]
    price_per_ticket = data["price_per_ticket"]
    t_emoji = data["t_emoji"]
    t_name = data["t_name"]

    total_cost = round(amount * price_per_ticket, 2)
    user = await queries.get_user_by_telegram_id(message.from_user.id)

    if user["points"] < total_cost:
        await message.answer(
            f"❌ Недостаточно баллов!\n\n"
            f"🎫 Нужно: <b>{total_cost:g}</b> баллов\n"
            f"💼 Ваш баланс: <b>{user['points']:g}</b> баллов",
            reply_markup=cancel_keyboard(),
            parse_mode="HTML"
        )
        return

    await state.update_data(amount=amount, total_cost=total_cost)
    await state.set_state(ShopExchange.confirm)

    await message.answer(
        f"🔄 <b>Подтвердите обмен</b>\n\n"
        f"⭐ Будет списано: <b>{total_cost:g}</b> баллов\n"
        f"🎫 Будет начислено: <b>{amount}</b> {t_emoji} {t_name} тикет(ов)\n\n"
        f"Подтвердить обмен?",
        reply_markup=confirm_exchange_keyboard(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "shop_exch_confirm")
async def shop_exchange_confirm(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    """Выполнение обмена баллов на тикеты."""
    data = await state.get_data()
    if not data or "ticket_key" not in data:
        await callback.answer("❌ Сессия устарела. Начните заново.", show_alert=True)
        await state.clear()
        return

    ticket_key = data["ticket_key"]
    amount = data["amount"]
    total_cost = data["total_cost"]
    t_emoji = data["t_emoji"]
    t_name = data["t_name"]

    user = await queries.get_user_by_telegram_id(callback.from_user.id)
    if not user or user.get("is_blocked"):
        await callback.answer("🚫 Доступ запрещён.", show_alert=True)
        return

    if user["points"] < total_cost:
        await callback.answer("❌ Недостаточно баллов!", show_alert=True)
        await state.clear()
        return

    ticket_type = f"tickets_{ticket_key}"

    # Списываем баллы
    await queries.update_user_balance(user["id"], "points", "subtract", total_cost)
    # Начисляем тикеты
    await queries.update_user_balance(user["id"], ticket_type, "add", amount)

    # Транзакции
    await queries.add_transaction(
        user_id=user["id"],
        currency_type="points",
        operation="subtract",
        amount=total_cost,
        reason=f"Обмен на {amount} {t_name} тикет(ов) в магазине",
        performed_by=callback.from_user.id
    )
    await queries.add_transaction(
        user_id=user["id"],
        currency_type=ticket_type,
        operation="add",
        amount=amount,
        reason=f"Обмен {total_cost:g} баллов на {t_name} тикеты в магазине",
        performed_by=callback.from_user.id
    )

    # Уведомление Owner
    date_str = datetime.now().strftime("%d.%m.%Y")
    try:
        await bot.send_message(
            OWNER_ID,
            f"🔔 <b>Обмен баллов на тикеты</b>\n\n"
            f"👤 Пользователь: <b>{user['nickname']}</b>\n"
            f"🆔 ID: <code>{user['telegram_id']}</code>\n"
            f"⭐ Списано: <b>{total_cost:g}</b> баллов\n"
            f"🎫 Начислено: <b>{amount}</b> {t_emoji} {t_name} тикет(ов)\n"
            f"📅 Дата: {date_str}",
            parse_mode="HTML"
        )
    except Exception as e:
        logger.warning(f"Не удалось отправить уведомление owner: {e}")

    updated = await queries.get_user_by_telegram_id(callback.from_user.id)
    await state.clear()

    await callback.message.edit_text(
        f"✅ <b>Обмен успешно выполнен!</b>\n\n"
        f"⭐ Списано: <b>{total_cost:g}</b> баллов\n"
        f"🎫 Начислено: <b>{amount}</b> {t_emoji} {t_name} тикет(ов)\n\n"
        f"💼 Баллы: <b>{updated['points']:g}</b>\n"
        f"🎫 {t_name} тикетов: <b>{updated.get(ticket_type, 0)}</b>",
        reply_markup=back_to_shop_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer("✅ Обмен выполнен!")
    logger.info(f"Shop exchange: {user['nickname']} обменял {total_cost:g} баллов на {amount} {t_name}")


# ──────────────────────────────────────────────
# Вывод баллов в деньги
# ──────────────────────────────────────────────

@router.callback_query(F.data == "shop_withdraw")
async def shop_withdraw_menu(callback: CallbackQuery, state: FSMContext) -> None:
    """Меню вывода баллов."""
    await state.clear()
    user = await queries.get_user_by_telegram_id(callback.from_user.id)
    if not user or user.get("is_blocked"):
        await callback.answer("🚫 Доступ запрещён.", show_alert=True)
        return

    settings = await queries.get_shop_settings()
    rate = float(settings.get("withdraw_rate", "9"))
    min_amount = float(settings.get("withdraw_min", "50"))

    await state.set_state(ShopWithdraw.waiting_amount)

    await callback.message.edit_text(
        f"💰 <b>Вывод баллов в деньги</b>\n\n"
        f"💼 Ваш баланс: <b>{user['points']:g}</b> баллов\n"
        f"💵 Курс: <b>1 балл = {rate:g} рублей</b>\n"
        f"⏩ Минимум: <b>{min_amount:g} баллов</b>\n\n"
        f"Введите количество баллов для вывода:",
        reply_markup=cancel_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(ShopWithdraw.waiting_amount)
async def shop_withdraw_amount(message: Message, state: FSMContext) -> None:
    """Обработка суммы для вывода."""
    try:
        amount = float(message.text.strip().replace(",", "."))
        if amount <= 0:
            raise ValueError
    except ValueError:
        await message.answer(
            "⚠️ Введите положительное число баллов.",
            reply_markup=cancel_keyboard()
        )
        return

    settings = await queries.get_shop_settings()
    rate = float(settings.get("withdraw_rate", "9"))
    min_amount = float(settings.get("withdraw_min", "50"))

    if amount < min_amount:
        await message.answer(
            f"❌ Минимальная сумма вывода: <b>{min_amount:g} баллов</b>",
            reply_markup=cancel_keyboard(),
            parse_mode="HTML"
        )
        return

    user = await queries.get_user_by_telegram_id(message.from_user.id)
    if user["points"] < amount:
        await message.answer(
            f"❌ Недостаточно баллов!\n\n"
            f"💼 Ваш баланс: <b>{user['points']:g}</b> баллов",
            reply_markup=cancel_keyboard(),
            parse_mode="HTML"
        )
        return

    payout = round(amount * rate, 2)
    await state.update_data(amount=amount, payout=payout, rate=rate)
    await state.set_state(ShopWithdraw.confirm)

    await message.answer(
        f"💰 <b>Подтвердите вывод</b>\n\n"
        f"⭐ Баллов к выводу: <b>{amount:g}</b>\n"
        f"💵 Сумма выплаты: <b>{payout:g} рублей</b>\n\n"
        f"Вы уверены?",
        reply_markup=confirm_withdraw_keyboard(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "shop_withdraw_confirm")
async def shop_withdraw_confirm(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    """Выполнение вывода баллов."""
    data = await state.get_data()
    if not data or "amount" not in data:
        await callback.answer("❌ Сессия устарела. Начните заново.", show_alert=True)
        await state.clear()
        return

    amount = data["amount"]
    payout = data["payout"]
    rate = data["rate"]

    user = await queries.get_user_by_telegram_id(callback.from_user.id)
    if not user or user.get("is_blocked"):
        await callback.answer("🚫 Доступ запрещён.", show_alert=True)
        return

    settings = await queries.get_shop_settings()
    min_amount = float(settings.get("withdraw_min", "50"))

    if user["points"] < amount:
        await callback.answer("❌ Недостаточно баллов!", show_alert=True)
        await state.clear()
        return

    if amount < min_amount:
        await callback.answer(f"❌ Минимум {min_amount:g} баллов!", show_alert=True)
        await state.clear()
        return

    # Списываем баллы
    await queries.update_user_balance(user["id"], "points", "subtract", amount)

    # Транзакция
    await queries.add_transaction(
        user_id=user["id"],
        currency_type="points",
        operation="subtract",
        amount=amount,
        reason=f"Вывод баллов: {amount:g} б. = {payout:g} руб.",
        performed_by=callback.from_user.id
    )

    # Создаём заявку в To-Do
    details = json.dumps({
        "type": "withdraw",
        "amount": amount,
        "payout": payout,
        "rate": rate,
        "user_nickname": user["nickname"],
        "user_telegram_id": user["telegram_id"],
    }, ensure_ascii=False)
    order_id = await queries.create_shop_order(user["id"], "withdraw", details)

    # Уведомление Owner
    date_str = datetime.now().strftime("%d.%m.%Y")
    try:
        await bot.send_message(
            OWNER_ID,
            f"🔔 <b>Заявка на вывод баллов</b>\n\n"
            f"👤 Пользователь: <b>{user['nickname']}</b>\n"
            f"🆔 ID: <code>{user['telegram_id']}</code>\n"
            f"⭐ Баллов: <b>{amount:g}</b>\n"
            f"💰 Сумма выплаты: <b>{payout:g} рублей</b>\n"
            f"📋 Заявка #<b>{order_id}</b>\n"
            f"📅 Дата: {date_str}",
            parse_mode="HTML"
        )
    except Exception as e:
        logger.warning(f"Не удалось отправить уведомление owner: {e}")

    updated = await queries.get_user_by_telegram_id(callback.from_user.id)
    owner = await queries.get_user_by_telegram_id(OWNER_ID)
    owner_username = owner.get("username") if owner else None
    await state.clear()

    await callback.message.edit_text(
        f"✅ <b>Заявка на выплату успешно создана!</b>\n\n"
        f"⭐ Списано: <b>{amount:g}</b> баллов\n"
        f"💰 К получению: <b>{payout:g} рублей</b>\n"
        f"💼 Остаток баллов: <b>{updated['points']:g}</b>\n\n"
        f"Для получения выплаты свяжитесь с владельцем.",
        reply_markup=contact_owner_keyboard(OWNER_ID, owner_username),
        parse_mode="HTML"
    )
    await callback.answer("✅ Заявка создана!")
    logger.info(f"Shop withdraw: {user['nickname']} вывел {amount:g} баллов = {payout:g} руб.")
