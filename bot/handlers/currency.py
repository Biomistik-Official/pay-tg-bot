"""
Обработчик меню Баллы / Тикеты.
"""

from aiogram import Router, F
from aiogram.types import CallbackQuery

from bot.database import queries
from bot.keyboards.user import currency_menu_keyboard

router = Router()


@router.callback_query(F.data == "currency_menu")
async def currency_menu(callback: CallbackQuery) -> None:
    """Показать меню баллов и тикетов."""
    user = await queries.get_user_by_telegram_id(callback.from_user.id)

    if not user:
        await callback.answer("Профиль не найден. Введите /start", show_alert=True)
        return

    if user.get("is_blocked"):
        await callback.answer("🚫 Ваш аккаунт заблокирован.", show_alert=True)
        return

    total_tickets = (
        user.get("tickets_platinum", 0) +
        user.get("tickets_gold", 0) +
        user.get("tickets_silver", 0) +
        user.get("tickets_bronze", 0) +
        user.get("tickets_support", 0) +
        user.get("tickets_help", 0)
    )
    text = (
        f"🎫⭐ <b>Баллы и Тикеты</b>\n\n"
        f"Ваш текущий баланс:\n\n"
        f"🎫 <b>Тикеты:</b> {total_tickets}\n"
        f"⭐ <b>Баллы:</b> {user['points']:g}\n\n"
        f"Выберите действие:"
    )
    await callback.message.edit_text(
        text,
        reply_markup=currency_menu_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()
