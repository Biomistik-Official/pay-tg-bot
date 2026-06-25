"""
Обработчики для проверки активности участников клубов (только для Owner).
"""

from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.config import config
from bot.utils.club_activity import (
    CLUB_TAGS,
    check_all_clubs_inactive,
    check_single_club_all_members,
    split_long_message,
)
from bot.utils.logger import logger

router = Router()

# Маппинг тегов клубов -> красивые названия (без обращения к API)
CLUB_DISPLAY = {
    "2UUQ0989V": "ViGarik Squad",
    "2CL9LRVCL": "ViGarik Academy",
    "2CP8R2Q8U": "ViGarik Events",
}


def _is_owner(telegram_id: int) -> bool:
    return telegram_id == config.owner_id


# ─── Клавиатуры ───────────────────────────────────────────────────────────────

def club_activity_main_keyboard() -> InlineKeyboardMarkup:
    """Главное меню раздела проверки активности."""
    builder = InlineKeyboardBuilder()
    for tag in CLUB_TAGS:
        name = CLUB_DISPLAY.get(tag, f"#{tag}")
        builder.row(InlineKeyboardButton(
            text=f"🏠 {name}",
            callback_data=f"ca_club:{tag}"
        ))
    builder.row(InlineKeyboardButton(
        text="🔍 Все неактивные (3+ д)",
        callback_data="ca_all_inactive"
    ))
    builder.row(InlineKeyboardButton(
        text="⬅️ Админ-панель",
        callback_data="admin_panel"
    ))
    return builder.as_markup()


def club_activity_back_keyboard() -> InlineKeyboardMarkup:
    """Кнопка возврата в меню активности."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="⬅️ Назад к клубам",
        callback_data="ca_menu"
    ))
    return builder.as_markup()


# ─── Вспомогательная функция отправки длинных ответов ─────────────────────────

async def _send_chunks(callback: CallbackQuery, text: str) -> None:
    """
    Разбивает текст на чанки и отправляет их.
    Первый чанк редактирует текущее сообщение, остальные — новые.
    """
    chunks = split_long_message(text, max_len=4000)
    back_kb = club_activity_back_keyboard()

    for i, chunk in enumerate(chunks):
        is_last = (i == len(chunks) - 1)
        kb = back_kb if is_last else None
        if i == 0:
            try:
                await callback.message.edit_text(chunk, parse_mode="HTML", reply_markup=kb)
            except Exception:
                await callback.message.answer(chunk, parse_mode="HTML", reply_markup=kb)
        else:
            await callback.message.answer(chunk, parse_mode="HTML", reply_markup=kb)


# ─── Обработчики ──────────────────────────────────────────────────────────────

@router.callback_query(F.data == "ca_menu")
async def show_ca_menu(callback: CallbackQuery) -> None:
    """Показывает главное меню раздела активности клубов."""
    if not _is_owner(callback.from_user.id):
        await callback.answer("⛔ Недостаточно прав.", show_alert=True)
        return

    text = (
        "📊 <b>Проверка активности участников</b>\n\n"
        "Выберите клуб для просмотра статуса всех участников,\n"
        "или запустите общую проверку неактивных (3+ дня).\n\n"
        "Статусы: 🟢 &lt;24ч | 🟡 1–2 дня | 🔴 3+ дней | ⚪ нет боёв"
    )
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=club_activity_main_keyboard())
    except Exception:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=club_activity_main_keyboard())
    await callback.answer()


@router.callback_query(F.data == "ca_all_inactive")
async def ca_all_inactive(callback: CallbackQuery) -> None:
    """Проверяет все клубы и выводит неактивных (3+ дня)."""
    if not _is_owner(callback.from_user.id):
        await callback.answer("⛔ Недостаточно прав.", show_alert=True)
        return

    await callback.answer()

    try:
        await callback.message.edit_text("⏳ Проверяю все клубы, подождите...", parse_mode="HTML")
    except Exception:
        pass

    try:
        result = await check_all_clubs_inactive()
        await _send_chunks(callback, result)
    except Exception as e:
        logger.error(f"[ClubActivity] Ошибка при проверке всех клубов: {e}", exc_info=True)
        try:
            await callback.message.edit_text(
                f"❌ Произошла ошибка:\n<code>{e}</code>",
                parse_mode="HTML",
                reply_markup=club_activity_back_keyboard()
            )
        except Exception:
            pass


@router.callback_query(F.data.startswith("ca_club:"))
async def ca_single_club(callback: CallbackQuery) -> None:
    """Показывает статус всех участников конкретного клуба."""
    if not _is_owner(callback.from_user.id):
        await callback.answer("⛔ Недостаточно прав.", show_alert=True)
        return

    club_tag = callback.data.split(":", 1)[1]
    club_name = CLUB_DISPLAY.get(club_tag, f"#{club_tag}")
    await callback.answer()

    try:
        await callback.message.edit_text(
            f"⏳ Загружаю данные клуба <b>{club_name}</b>...",
            parse_mode="HTML"
        )
    except Exception:
        pass

    try:
        result = await check_single_club_all_members(club_tag)
        await _send_chunks(callback, result)
    except Exception as e:
        logger.error(f"[ClubActivity] Ошибка при проверке клуба #{club_tag}: {e}", exc_info=True)
        try:
            await callback.message.edit_text(
                f"❌ Произошла ошибка:\n<code>{e}</code>",
                parse_mode="HTML",
                reply_markup=club_activity_back_keyboard()
            )
        except Exception:
            pass
