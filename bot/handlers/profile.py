"""
Обработчик профиля пользователя.
"""

from aiogram import Router, F
from aiogram.types import CallbackQuery

from bot.database import queries
from bot.keyboards.user import back_to_main_keyboard
from bot.utils.formatters import format_datetime, format_profile

router = Router()


async def build_profile_text(user: dict) -> str:
    """Собрать профиль вместе с данными Staff."""
    text = format_profile(user)
    if not await queries.get_staff_by_user_id(user["id"]):
        return text

    activity = await queries.get_staff_activity(user["id"])
    treasury = await queries.get_user_treasury(user["id"])
    treasury_name = f"{treasury['emoji']} {treasury['name']}" if treasury else "Не назначена"
    last_activity = (
        format_datetime(activity["last_activity_at"])
        if activity["last_activity_at"] else "—"
    )
    return text + (
        "\n\n🛠 <b>Staff</b>\n"
        f"🏦 <b>Казна:</b> {treasury_name}\n"
        "📊 <b>Активности Staff</b>\n"
        f"  Показатель: <b>{activity['activity_count']}</b>\n"
        f"  Заработано баллов: <b>{activity['earned_points']:g}</b>\n"
        f"  Заработано тикетов: <b>{activity['earned_tickets']:g}</b>\n"
        f"  Последняя активность: <b>{last_activity}</b>"
    )


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

    text = await build_profile_text(user)
    await callback.message.edit_text(
        text,
        reply_markup=back_to_main_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()
