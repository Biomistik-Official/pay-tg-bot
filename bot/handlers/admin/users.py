"""
Управление пользователями (Admin).
"""

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from bot.config import config
from bot.database import queries
from bot.keyboards.admin import (
    admin_users_keyboard,
    admin_back_keyboard,
    admin_panel_keyboard,
    user_profile_admin_keyboard,
    cancel_admin_keyboard,
    user_moderation_keyboard,
)
from bot.states.forms import SearchUser, ChangeNickname, ChangePlayerTag, ManageModeration
from bot.utils.formatters import format_profile
from bot.utils.logger import log_admin_action
from bot.utils.brawlstars import BrawlStarsClient, BrawlStarsAPIError, ALLOWED_CLUBS

router = Router()


def _is_owner(callback: CallbackQuery) -> bool:
    return callback.from_user.id == config.owner_id


@router.callback_query(F.data.in_({"admin_users"}) | F.data.startswith("admin_users_page:"))
async def admin_users_menu(callback: CallbackQuery) -> None:
    """Меню управления пользователями с алфавитным списком."""
    if not _is_owner(callback):
        await callback.answer("⛔ Доступ запрещён.", show_alert=True)
        return

    offset = 0
    if callback.data.startswith("admin_users_page:"):
        offset = int(callback.data.split(":")[1])

    PAGE_SIZE = 10
    total = await queries.count_users()
    users = await queries.get_users_sorted(limit=PAGE_SIZE, offset=offset)

    text = "👥 <b>Управление пользователями</b>\n\n"
    if total > 0:
        text += f"Показаны пользователи {offset + 1} - {min(offset + PAGE_SIZE, total)} из {total}.\n"
        text += "Выберите пользователя для просмотра профиля:"
    else:
        text += "Пользователей пока нет в базе данных."

    await callback.message.edit_text(
        text,
        reply_markup=admin_users_keyboard(users=users, offset=offset, total=total, page_size=PAGE_SIZE),
        parse_mode="HTML"
    )
    await callback.answer()


# ──────────────────────────────────────────────
# Поиск пользователя
# ──────────────────────────────────────────────

@router.callback_query(F.data == "search_user_nick")
async def search_by_nick(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_owner(callback):
        await callback.answer("⛔ Доступ запрещён.", show_alert=True)
        return

    await state.set_state(SearchUser.waiting_query)
    await state.update_data(search_type="nick")
    await callback.message.edit_text(
        "🔍 <b>Поиск по нику</b>\n\nВведите никнейм пользователя (или часть):",
        reply_markup=cancel_admin_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "search_user_id")
async def search_by_id(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_owner(callback):
        await callback.answer("⛔ Доступ запрещён.", show_alert=True)
        return

    await state.set_state(SearchUser.waiting_query)
    await state.update_data(search_type="id")
    await callback.message.edit_text(
        "🔍 <b>Поиск по Telegram ID</b>\n\nВведите Telegram ID пользователя:",
        reply_markup=cancel_admin_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(SearchUser.waiting_query)
async def process_search(message: Message, state: FSMContext) -> None:
    """Обработать запрос поиска пользователя."""
    data = await state.get_data()
    search_type = data.get("search_type", "nick")
    query = message.text.strip()
    await state.clear()

    user = None
    if search_type == "id":
        try:
            tg_id = int(query)
            user = await queries.get_user_by_telegram_id(tg_id)
        except ValueError:
            await message.answer(
                "⚠️ Telegram ID должен быть числом.",
                reply_markup=admin_back_keyboard()
            )
            return
    else:
        user = await queries.get_user_by_nickname(query)

    if not user:
        await message.answer(
            "❌ <b>Пользователь не найден.</b>",
            reply_markup=admin_back_keyboard(),
            parse_mode="HTML"
        )
        return

    text = format_profile(user)
    await message.answer(
        text,
        reply_markup=user_profile_admin_keyboard(
            user["telegram_id"], bool(user["is_blocked"])
        ),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("view_user:"))
async def view_user(callback: CallbackQuery) -> None:
    """Показать профиль пользователя по Telegram ID."""
    if not _is_owner(callback):
        await callback.answer("⛔ Доступ запрещён.", show_alert=True)
        return

    telegram_id = int(callback.data.split(":")[1])
    user = await queries.get_user_by_telegram_id(telegram_id)

    if not user:
        await callback.answer("Пользователь не найден.", show_alert=True)
        return

    text = format_profile(user)
    await callback.message.edit_text(
        text,
        reply_markup=user_profile_admin_keyboard(
            user["telegram_id"], bool(user["is_blocked"])
        ),
        parse_mode="HTML"
    )
    await callback.answer()


# ──────────────────────────────────────────────
# Блокировка / Разблокировка
# ──────────────────────────────────────────────

@router.callback_query(F.data.startswith("block_user:"))
async def block_user(callback: CallbackQuery, bot: Bot) -> None:
    if not _is_owner(callback):
        await callback.answer("⛔ Доступ запрещён.", show_alert=True)
        return

    telegram_id = int(callback.data.split(":")[1])
    await queries.set_user_blocked(telegram_id, True)

    user = await queries.get_user_by_telegram_id(telegram_id)
    log_admin_action(callback.from_user.id, "BLOCK_USER", f"TG:{telegram_id} ({user['nickname']})")

    # Уведомляем пользователя
    try:
        await bot.send_message(telegram_id, "🚫 Ваш аккаунт был заблокирован администратором.")
    except Exception:
        pass

    await callback.answer("✅ Пользователь заблокирован.", show_alert=True)
    await view_user(callback)


@router.callback_query(F.data.startswith("unblock_user:"))
async def unblock_user(callback: CallbackQuery, bot: Bot) -> None:
    if not _is_owner(callback):
        await callback.answer("⛔ Доступ запрещён.", show_alert=True)
        return

    telegram_id = int(callback.data.split(":")[1])
    await queries.set_user_blocked(telegram_id, False)

    user = await queries.get_user_by_telegram_id(telegram_id)
    log_admin_action(callback.from_user.id, "UNBLOCK_USER", f"TG:{telegram_id} ({user['nickname']})")

    # Уведомляем пользователя
    try:
        await bot.send_message(telegram_id, "✅ Ваш аккаунт был разблокирован.")
    except Exception:
        pass

    await callback.answer("✅ Пользователь разблокирован.", show_alert=True)
    await view_user(callback)


# ──────────────────────────────────────────────
# Изменение никнейма
# ──────────────────────────────────────────────

@router.callback_query(F.data.startswith("change_nick:"))
async def change_nickname_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_owner(callback):
        await callback.answer("⛔ Доступ запрещён.", show_alert=True)
        return

    telegram_id = int(callback.data.split(":")[1])
    await state.set_state(ChangeNickname.waiting_new_nickname)
    await state.update_data(target_telegram_id=telegram_id)

    await callback.message.edit_text(
        "✏️ <b>Изменение никнейма</b>\n\nВведите новый никнейм пользователя:",
        reply_markup=cancel_admin_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(ChangeNickname.waiting_new_nickname)
async def process_change_nickname(message: Message, state: FSMContext) -> None:
    new_nickname = message.text.strip()
    if len(new_nickname) < 2 or len(new_nickname) > 50:
        await message.answer(
            "⚠️ Никнейм должен быть от 2 до 50 символов.",
            reply_markup=cancel_admin_keyboard()
        )
        return

    data = await state.get_data()
    telegram_id = data["target_telegram_id"]
    await state.clear()

    await queries.update_user_nickname(telegram_id, new_nickname)
    user = await queries.get_user_by_telegram_id(telegram_id)
    log_admin_action(message.from_user.id, "CHANGE_NICKNAME", f"TG:{telegram_id} → {new_nickname}")

    await message.answer(
        f"✅ Никнейм изменён на <b>{new_nickname}</b>",
        parse_mode="HTML"
    )
    await message.answer(
        format_profile(user),
        reply_markup=user_profile_admin_keyboard(
            user["telegram_id"], bool(user["is_blocked"])
        ),
        parse_mode="HTML"
    )


# ──────────────────────────────────────────────
# Изменение тега Brawl Stars
# ──────────────────────────────────────────────

@router.callback_query(F.data.startswith("change_tag:"))
async def change_tag_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_owner(callback):
        await callback.answer("⛔ Доступ запрещён.", show_alert=True)
        return

    telegram_id = int(callback.data.split(":")[1])
    await state.set_state(ChangePlayerTag.waiting_new_tag)
    await state.update_data(target_telegram_id=telegram_id)

    await callback.message.edit_text(
        "🏷️ <b>Изменение тега Brawl Stars</b>\n\nВведите новый тег игрока (например, #ABC123XYZ):",
        reply_markup=cancel_admin_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(ChangePlayerTag.waiting_new_tag)
async def process_change_tag(message: Message, state: FSMContext) -> None:
    new_tag = message.text.strip().upper()
    if not new_tag.startswith("#"):
        new_tag = "#" + new_tag

    data = await state.get_data()
    telegram_id = data["target_telegram_id"]

    # Проверка на дублирование тега
    existing = await queries.get_user_by_player_tag(new_tag)
    if existing and existing["telegram_id"] != telegram_id:
        await message.answer(
            "❌ Этот тег Brawl Stars уже привязан к другому пользователю.",
            reply_markup=cancel_admin_keyboard()
        )
        return

    await state.clear()
    
    # Пытаемся получить данные о новом теге через API
    client = BrawlStarsClient()
    checking_msg = await message.answer("⏳ Проверяем тег игрока через API Brawl Stars...")
    
    try:
        player_data = await client.get_player(new_tag)
        if not player_data:
            await checking_msg.edit_text(
                "❌ Игрок с таким тегом не найден в Brawl Stars API.",
                reply_markup=admin_back_keyboard()
            )
            return
        
        club = player_data.get("club") or {}
        club_tag = club.get("tag")
        club_name = club.get("name")
        
        in_allowed_club = False
        if club_tag:
            norm_club_tag = club_tag.strip().upper()
            if norm_club_tag in ALLOWED_CLUBS:
                in_allowed_club = True
        
        # Обновляем тег и название клуба в БД
        await queries.update_user_player_tag(telegram_id, new_tag, club_name)
        
        user = await queries.get_user_by_telegram_id(telegram_id)
        is_currently_blocked = user.get("is_blocked", 0)
        
        status_msg = ""
        if in_allowed_club:
            if is_currently_blocked == 2:
                # Разблокируем
                await queries.set_user_blocked(telegram_id, 0)
                status_msg = "\n✅ Доступ к боту восстановлен, так как игрок состоит в разрешенном клубе."
                user = await queries.get_user_by_telegram_id(telegram_id)
        else:
            # Если игрок не в клубе, то ставим блокировку (если не заблокирован вручную)
            if is_currently_blocked == 0:
                await queries.set_user_blocked(telegram_id, 2)
                status_msg = "\n❌ Доступ к боту временно отключён, так как игрок не состоит в разрешенных клубах."
                user = await queries.get_user_by_telegram_id(telegram_id)
        
        log_admin_action(message.from_user.id, "CHANGE_PLAYER_TAG", f"TG:{telegram_id} → {new_tag} ({club_name})")
        
        await checking_msg.edit_text(
            f"✅ Тег игрока изменён на <b>{new_tag}</b> (Клуб: {club_name or 'нет'}){status_msg}",
            parse_mode="HTML"
        )
        await message.answer(
            format_profile(user),
            reply_markup=user_profile_admin_keyboard(
                user["telegram_id"], bool(user["is_blocked"])
            ),
            parse_mode="HTML"
        )
        
    except BrawlStarsAPIError as e:
        await checking_msg.edit_text(
            f"❌ Ошибка Brawl Stars API: {e}",
            reply_markup=admin_back_keyboard()
        )


# ──────────────────────────────────────────────
# История операций пользователя (для Admin)
# ──────────────────────────────────────────────

@router.callback_query(F.data.startswith("user_history:"))
async def view_user_history(callback: CallbackQuery) -> None:
    if not _is_owner(callback):
        await callback.answer("⛔ Доступ запрещён.", show_alert=True)
        return

    parts = callback.data.split(":")
    telegram_id = int(parts[1])
    offset = int(parts[2])
    PAGE_SIZE = 5

    user = await queries.get_user_by_telegram_id(telegram_id)
    if not user:
        await callback.answer("Пользователь не найден.", show_alert=True)
        return

    from bot.keyboards.admin import user_history_nav_keyboard
    from bot.utils.formatters import format_transaction

    total = await queries.count_user_transactions(user["id"])
    transactions = await queries.get_user_transactions(user["id"], limit=PAGE_SIZE, offset=offset)

    if not transactions:
        await callback.message.edit_text(
            f"📊 <b>История операций</b>\n👤 {user['nickname']}\n\nОпераций нет.",
            reply_markup=user_history_nav_keyboard(telegram_id, offset, total, PAGE_SIZE),
            parse_mode="HTML"
        )
        await callback.answer()
        return

    lines = [f"📊 <b>История: {user['nickname']}</b> (стр. {offset // PAGE_SIZE + 1})\n"]
    for tx in transactions:
        lines.append(f"\n{format_transaction(tx)}")
        lines.append("─" * 28)

    text = "\n".join(lines).rstrip("─").rstrip()

    await callback.message.edit_text(
        text,
        reply_markup=user_history_nav_keyboard(telegram_id, offset, total, PAGE_SIZE),
        parse_mode="HTML"
    )
    await callback.answer()


# ──────────────────────────────────────────────
# Модерация (Анварны и Анмуты)
# ──────────────────────────────────────────────

@router.callback_query(F.data.startswith("user_moderation:"))
async def user_moderation(callback: CallbackQuery) -> None:
    if not _is_owner(callback):
        await callback.answer("⛔ Доступ запрещён.", show_alert=True)
        return

    telegram_id = int(callback.data.split(":")[1])
    user = await queries.get_user_by_telegram_id(telegram_id)
    if not user:
        await callback.answer("Пользователь не найден.", show_alert=True)
        return

    text = (
        f"⚖️ <b>Модерация пользователя</b>\n"
        f"👤 {user['nickname']} (ID: {telegram_id})\n\n"
        f"⚠️ Анварны: <b>{user.get('unwarns', 0)}</b>\n"
        f"🔇 Анмуты: <b>{user.get('unmutes', 0)}</b>\n\n"
        f"Выберите действие:"
    )
    await callback.message.edit_text(
        text,
        reply_markup=user_moderation_keyboard(telegram_id),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("give_unwarn:") | F.data.startswith("take_unwarn:") | F.data.startswith("give_unmute:") | F.data.startswith("take_unmute:"))
async def quick_moderation_action(callback: CallbackQuery) -> None:
    if not _is_owner(callback):
        await callback.answer("⛔ Доступ запрещён.", show_alert=True)
        return

    parts = callback.data.split(":")
    action = parts[0]
    telegram_id = int(parts[1])

    user = await queries.get_user_by_telegram_id(telegram_id)
    if not user:
        await callback.answer("Пользователь не найден.", show_alert=True)
        return

    currency_type = "unwarns" if "unwarn" in action else "unmutes"
    operation = "add" if "give" in action else "subtract"

    # Выдаем или забираем 1 штуку
    if operation == "subtract" and user.get(currency_type, 0) <= 0:
        await callback.answer("❌ Баланс не может быть меньше нуля.", show_alert=True)
        return

    await queries.update_user_balance(user["id"], currency_type, operation, 1)
    await queries.add_transaction(user["id"], currency_type, operation, 1, performed_by=callback.from_user.id)

    mod_type = "Анварн" if currency_type == "unwarns" else "Анмут"
    op_text = "выдан" if operation == "add" else "снят"
    log_admin_action(callback.from_user.id, f"{operation.upper()}_{currency_type.upper()}", f"TG:{telegram_id} 1 {mod_type}")

    await callback.answer(f"✅ {mod_type} {op_text}.", show_alert=True)
    await user_moderation(callback)


@router.callback_query(F.data.startswith("set_unwarn:") | F.data.startswith("set_unmute:"))
async def set_moderation_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_owner(callback):
        await callback.answer("⛔ Доступ запрещён.", show_alert=True)
        return

    parts = callback.data.split(":")
    action = parts[0]
    telegram_id = int(parts[1])

    currency_type = "unwarns" if "unwarn" in action else "unmutes"
    mod_name = "Анварнов" if currency_type == "unwarns" else "Анмутов"

    await state.set_state(ManageModeration.waiting_amount)
    await state.update_data(target_telegram_id=telegram_id, currency_type=currency_type)

    await callback.message.edit_text(
        f"✏️ <b>Установка значения</b>\n\nВведите новое количество {mod_name}:",
        reply_markup=cancel_admin_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(ManageModeration.waiting_amount)
async def process_set_moderation(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    telegram_id = data["target_telegram_id"]
    currency_type = data["currency_type"]

    try:
        amount = int(message.text.strip())
        if amount < 0:
            raise ValueError
    except ValueError:
        await message.answer("⚠️ Введите корректное положительное число или 0.", reply_markup=cancel_admin_keyboard())
        return

    await state.clear()
    user = await queries.get_user_by_telegram_id(telegram_id)
    if not user:
        await message.answer("❌ Пользователь не найден.")
        return

    await queries.update_user_balance(user["id"], currency_type, "set", amount)
    await queries.add_transaction(user["id"], currency_type, "set", amount, performed_by=message.from_user.id)

    mod_type = "Анварнов" if currency_type == "unwarns" else "Анмутов"
    log_admin_action(message.from_user.id, f"SET_{currency_type.upper()}", f"TG:{telegram_id} = {amount}")

    await message.answer(f"✅ Установлено {amount} {mod_type} для пользователя <b>{user['nickname']}</b>.", parse_mode="HTML")

    # Перерисовываем профиль
    updated_user = await queries.get_user_by_telegram_id(telegram_id)
    await message.answer(
        format_profile(updated_user),
        reply_markup=user_profile_admin_keyboard(updated_user["telegram_id"], bool(updated_user["is_blocked"])),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "cancel_admin_form")
async def cancel_admin_form(callback: CallbackQuery, state: FSMContext) -> None:
    """Отмена любой формы в Админ-панели."""
    await state.clear()
    await callback.message.edit_text(
        "👑 <b>Админ-панель</b>\n\nВыберите раздел:",
        reply_markup=admin_panel_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer("Отменено")
