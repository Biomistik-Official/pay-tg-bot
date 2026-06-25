"""
Рассылки (Owner only): глобальные и для Staff.
"""
import asyncio
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext

from bot.config import config
from bot.database import queries
from bot.keyboards.admin import (
    announcement_type_keyboard,
    confirm_announcement_keyboard,
    admin_back_keyboard,
)
from bot.states.forms import AdminAnnouncement

router = Router()


def _is_owner(uid: int) -> bool:
    return uid == config.owner_id


@router.callback_query(F.data == "admin_announcements")
async def show_announcement_menu(callback: CallbackQuery) -> None:
    if not _is_owner(callback.from_user.id):
        return await callback.answer("No access.", show_alert=True)
    await callback.message.edit_text(
        "\U0001f4ec <b>Объявления</b>\n\nВыберите тип рассылки:",
        reply_markup=announcement_type_keyboard(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("announce_type:"))
async def choose_announce_type(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_owner(callback.from_user.id):
        return await callback.answer("No access.", show_alert=True)
    ann_type = callback.data.split(":")[1]   # global | staff
    await state.update_data(ann_type=ann_type)
    await state.set_state(AdminAnnouncement.waiting_text)
    label = "\U0001f310 всем пользователям" if ann_type == "global" else "\U0001f6e0 только Staff"
    await callback.message.edit_text(
        f"\U0001f4ec <b>Объявление ({label})</b>\n\nВведите текст объявления:",
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(AdminAnnouncement.waiting_text)
async def receive_announce_text(message: Message, state: FSMContext) -> None:
    if not _is_owner(message.from_user.id):
        return
    text = message.text or message.caption or ""
    if not text.strip():
        return await message.answer("\u26a0\ufe0f Текст не может быть пустым. Попробуйте ещё раз.")
        
    data = await state.get_data()
    ann_type = data.get("ann_type", "global")
        
    owner = await queries.get_user_by_telegram_id(message.from_user.id)
    owner_name = f"@{owner['username']}" if owner and owner.get('username') else "Администрации"
    
    header = "Внимание, глобальное объявление!" if ann_type == "global" else "Внимание, объявление для стаффа!"
    
    formatted_text = (
        f"📣 <b>{header}</b>\n"
        f"👤 От: {owner_name}\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"{text}\n\n"
        f"━━━━━━━━━━━━━━━━━━"
    )

    await state.update_data(ann_text=formatted_text)
    await state.set_state(AdminAnnouncement.confirm)
    
    label = "\U0001f310 Всем" if ann_type == "global" else "\U0001f6e0 Staff"
    
    await message.answer(
        f"<b>Предпросмотр объявления [{label}]:</b>\n\n{formatted_text}\n\n"
        "Отправить?",
        reply_markup=confirm_announcement_keyboard(ann_type),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("announce_confirm:"))
async def send_announcement(callback: CallbackQuery, state: FSMContext, bot) -> None:
    if not _is_owner(callback.from_user.id):
        return await callback.answer("No access.", show_alert=True)
    data = await state.get_data()
    ann_type = callback.data.split(":")[1]
    text = data.get("ann_text", "")
    await state.clear()

    if ann_type == "global":
        ids = await queries.get_all_users_telegram_ids()
    else:
        ids = await queries.get_staff_telegram_ids()

    await callback.message.edit_text(
        f"\u23f3 Рассылка запущена... ({len(ids)} получателей)",
        parse_mode="HTML",
    )
    await callback.answer()

    ok = 0
    fail = 0
    for uid in ids:
        try:
            await bot.send_message(uid, text, parse_mode="HTML")
            ok += 1
        except Exception:
            fail += 1
        await asyncio.sleep(0.05)

    await callback.message.answer(
        f"\u2705 Рассылка завершена.\n"
        f"Отправлено: <b>{ok}</b>\n"
        f"Ошибок: <b>{fail}</b>",
        reply_markup=announcement_type_keyboard(),
        parse_mode="HTML",
    )
