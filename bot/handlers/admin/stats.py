"""
Статистика системы (Admin).
"""

from aiogram import Router, F
from aiogram.types import CallbackQuery

from bot.config import config
from bot.database import queries
from bot.keyboards.admin import admin_back_keyboard

router = Router()


@router.callback_query(F.data == "admin_stats")
async def show_stats(callback: CallbackQuery) -> None:
    """Показать общую статистику системы."""
    if callback.from_user.id != config.owner_id:
        await callback.answer("⛔ Доступ запрещён.", show_alert=True)
        return

    stats = await queries.get_statistics()

    text = (
        "📊 <b>Статистика системы</b>\n\n"
        f"👥 <b>Всего пользователей:</b> {stats['total_users']}\n"
        f"🎫 <b>Всего тикетов:</b> {stats['total_tickets']} шт.\n"
        f"  💎 Платиновых: {stats['tickets_platinum']}\n"
        f"  🥇 Золотых: {stats['tickets_gold']}\n"
        f"  🥈 Серебряных: {stats['tickets_silver']}\n"
        f"  🥉 Бронзовых: {stats['tickets_bronze']}\n"
        f"  🎁 Вспомогательных: {stats['tickets_support']}\n"
        f"  💪 Хелп тикетов: {stats['tickets_help']}\n"
        f"⭐ <b>Баллов в системе:</b> {stats['total_points']:g}\n\n"
        f"📨 <b>Всего заявок:</b> {stats['total_requests']}\n"
        f"✅ <b>Одобрено:</b> {stats['approved']}\n"
        f"❌ <b>Отклонено:</b> {stats['rejected']}\n"
        f"📅 <b>За последние 30 дней:</b> {stats['last_30_days']}"
    )

    await callback.message.edit_text(
        text,
        reply_markup=admin_back_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()
