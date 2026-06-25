"""
Главная страница Админ-панели.
"""

from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.filters import Filter

from bot.config import config
from bot.keyboards.admin import admin_panel_keyboard

router = Router()


class IsOwner(Filter):
    """Фильтр: только Owner имеет доступ."""
    async def __call__(self, event: CallbackQuery) -> bool:
        return event.from_user.id == config.owner_id


@router.callback_query(IsOwner(), F.data == "admin_panel")
async def show_admin_panel(callback: CallbackQuery) -> None:
    """Показать главную панель администратора."""
    text = (
        "👑 <b>Админ-панель</b>\n\n"
        "Добро пожаловать, <b>Owner</b>!\n"
        "Выберите раздел для управления:"
    )
    kb = admin_panel_keyboard()
    
    if callback.message.photo:
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.message.answer(text, reply_markup=kb, parse_mode="HTML")
    else:
        try:
            await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        except Exception:
            await callback.message.answer(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()
