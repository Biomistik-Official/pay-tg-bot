"""
Обработчик истории операций пользователя.
Поддерживает раздельную историю: тикеты и баллы.
"""

from aiogram import Router, F
from aiogram.types import CallbackQuery

from bot.database import queries
from bot.keyboards.user import (
    history_navigation_keyboard,
    history_tickets_nav_keyboard,
    history_points_nav_keyboard,
    back_to_tickets_keyboard,
    back_to_points_keyboard,
    back_to_currency_keyboard,
)
from bot.utils.formatters import format_transaction

router = Router()

PAGE_SIZE = 5


@router.callback_query(F.data.startswith("history:"))
async def show_history(callback: CallbackQuery) -> None:
    """Показать общую историю операций (для совместимости)."""
    offset = int(callback.data.split(":")[1])

    user = await queries.get_user_by_telegram_id(callback.from_user.id)
    if not user:
        await callback.answer("Профиль не найден.", show_alert=True)
        return

    total = await queries.count_user_transactions(user["id"])
    transactions = await queries.get_user_transactions(user["id"], limit=PAGE_SIZE, offset=offset)

    if not transactions:
        await callback.message.edit_text(
            "📊 <b>История операций</b>\n\n"
            "У вас пока нет ни одной операции.",
            reply_markup=back_to_currency_keyboard(),
            parse_mode="HTML"
        )
        await callback.answer()
        return

    lines = [f"📊 <b>История операций</b> (стр. {offset // PAGE_SIZE + 1})\n"]
    for tx in transactions:
        lines.append(f"\n{format_transaction(tx)}")
        lines.append("─" * 28)

    text = "\n".join(lines).rstrip("─").rstrip()

    await callback.message.edit_text(
        text,
        reply_markup=history_navigation_keyboard(offset, total, PAGE_SIZE),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("history_tickets:"))
async def show_history_tickets(callback: CallbackQuery) -> None:
    """История операций только по тикетам."""
    offset = int(callback.data.split(":")[1])

    user = await queries.get_user_by_telegram_id(callback.from_user.id)
    if not user:
        await callback.answer("Профиль не найден.", show_alert=True)
        return

    total = await queries.count_user_transactions_by_type(user["id"], "tickets")
    transactions = await queries.get_user_transactions_by_type(user["id"], "tickets", limit=PAGE_SIZE, offset=offset)

    if not transactions:
        await callback.message.edit_text(
            "🎫 <b>История тикетов</b>\n\n"
            "У вас пока нет операций по тикетам.",
            reply_markup=back_to_tickets_keyboard(),
            parse_mode="HTML"
        )
        await callback.answer()
        return

    lines = [f"🎫 <b>История тикетов</b> (стр. {offset // PAGE_SIZE + 1})\n"]
    for tx in transactions:
        lines.append(f"\n{format_transaction(tx)}")
        lines.append("─" * 28)

    text = "\n".join(lines).rstrip("─").rstrip()

    await callback.message.edit_text(
        text,
        reply_markup=history_tickets_nav_keyboard(offset, total, PAGE_SIZE),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("history_points:"))
async def show_history_points(callback: CallbackQuery) -> None:
    """История операций только по баллам."""
    offset = int(callback.data.split(":")[1])

    user = await queries.get_user_by_telegram_id(callback.from_user.id)
    if not user:
        await callback.answer("Профиль не найден.", show_alert=True)
        return

    total = await queries.count_user_transactions_by_type(user["id"], "points")
    transactions = await queries.get_user_transactions_by_type(user["id"], "points", limit=PAGE_SIZE, offset=offset)

    if not transactions:
        await callback.message.edit_text(
            "⭐ <b>История баллов</b>\n\n"
            "У вас пока нет операций по баллам.",
            reply_markup=back_to_points_keyboard(),
            parse_mode="HTML"
        )
        await callback.answer()
        return

    lines = [f"⭐ <b>История баллов</b> (стр. {offset // PAGE_SIZE + 1})\n"]
    for tx in transactions:
        lines.append(f"\n{format_transaction(tx)}")
        lines.append("─" * 28)

    text = "\n".join(lines).rstrip("─").rstrip()

    await callback.message.edit_text(
        text,
        reply_markup=history_points_nav_keyboard(offset, total, PAGE_SIZE),
        parse_mode="HTML"
    )
    await callback.answer()
