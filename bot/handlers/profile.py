"""
Обработчик профиля пользователя.
"""

from aiogram import Router, F
from aiogram.types import CallbackQuery

from bot.database import queries
from bot.keyboards.user import back_to_main_keyboard
from bot.utils.formatters import format_profile

router = Router()


@router.callback_query(F.data == "profile")
async def show_profile(callback: CallbackQuery) -> None:
    """Показать профиль пользователя."""
    user = await queries.get_user_by_telegram_id(callback.from_user.id)

    if not user:
        await callback.answer("Профиль не найден. Введите /start", show_alert=True)
        return

    if user.get("is_blocked"):
        await callback.answer("🚫 Ваш аккаунт заблокирован.", show_alert=True)
        return

    text = format_profile(user)
    await callback.message.edit_text(
        text,
        reply_markup=back_to_main_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()
