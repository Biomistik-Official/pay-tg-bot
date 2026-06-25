from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext

from bot.config import config
from bot.database import queries
from bot.keyboards.user import main_menu_keyboard, registration_keyboard, cancel_keyboard
from bot.states.forms import Registration
from bot.utils.logger import logger
from bot.utils.brawlstars import BrawlStarsClient, BrawlStarsAPIError, ALLOWED_CLUBS

router = Router()


async def show_main_menu(target, user: dict) -> None:
    """Показать главное меню (для Message или CallbackQuery)."""
    is_owner = user["telegram_id"] == config.owner_id
    is_staff = await queries.is_staff(user["telegram_id"])
    total_tickets = (
        user.get("tickets_platinum", 0) +
        user.get("tickets_gold", 0) +
        user.get("tickets_silver", 0) +
        user.get("tickets_bronze", 0) +
        user.get("tickets_support", 0) +
        user.get("tickets_help", 0)
    )
    text = (
        f"🏆 <b>VGS Money</b>\n\n"
        f"Добро пожаловать, <b>{user['nickname']}</b>!\n\n"
        f"🎫 Тикеты: <b>{total_tickets}</b>\n"
        f"⭐ Баллы: <b>{user['points']:g}</b>\n\n"
        f"Выберите раздел:"
    )
    kb = main_menu_keyboard(is_owner=is_owner, is_staff=is_staff)

    if isinstance(target, CallbackQuery):
        await target.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        await target.answer()
    else:
        await target.answer(text, reply_markup=kb, parse_mode="HTML")


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    """Обработка команды /start."""
    await state.clear()

    # Проверяем, зарегистрирован ли пользователь
    user = await queries.get_user_by_telegram_id(message.from_user.id)

    if not user:
        # Новый пользователь — предлагаем регистрацию
        await message.answer(
            "🏆 <b>Добро пожаловать в VGS Money!</b>\n\n"
            "Это система управления внутренней валютой.\n\n"
            "Для начала работы необходимо зарегистрироваться.",
            reply_markup=registration_keyboard(),
            parse_mode="HTML"
        )
        return

    # Обновляем username если изменился
    if user.get("username") != message.from_user.username:
        await queries.update_username(message.from_user.id, message.from_user.username)
        user = await queries.get_user_by_telegram_id(message.from_user.id)

    # Проверяем блокировку
    if user.get("is_blocked") == 1:
        await message.answer("🚫 Ваш аккаунт заблокирован. Обратитесь к владельцу.")
        return
    elif user.get("is_blocked") == 2:
        await message.answer(
            "❌ <b>Ваш доступ временно отключён.</b>\n\n"
            "Причина:\n"
            "Вы больше не состоите в одном из клубов системы.",
            parse_mode="HTML"
        )
        return

    await show_main_menu(message, user)


@router.callback_query(F.data == "start_registration")
async def start_registration(callback: CallbackQuery, state: FSMContext) -> None:
    """Начало процесса регистрации."""
    await state.set_state(Registration.waiting_nickname)
    await callback.message.edit_text(
        "✏️ <b>Введите ваш собственный никнейм для системы бота:</b>",
        reply_markup=cancel_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(Registration.waiting_nickname)
async def process_nickname(message: Message, state: FSMContext) -> None:
    """Обработка введённого никнейма."""
    nickname = message.text.strip()

    # Валидация никнейма
    if len(nickname) < 2:
        await message.answer(
            "⚠️ Никнейм слишком короткий. Минимум 2 символа. Попробуйте еще раз:",
            reply_markup=cancel_keyboard()
        )
        return

    if len(nickname) > 50:
        await message.answer(
            "⚠️ Никнейм слишком длинный. Максимум 50 символов. Попробуйте еще раз:",
            reply_markup=cancel_keyboard()
        )
        return

    await state.update_data(nickname=nickname)
    await state.set_state(Registration.waiting_player_tag)
    await message.answer(
        "🏷️ <b>Введите тег вашего игрока Brawl Stars:</b>\n\n"
        "<i>Например: #ABC123XYZ</i>",
        reply_markup=cancel_keyboard(),
        parse_mode="HTML"
    )


@router.message(Registration.waiting_player_tag)
async def process_player_tag(message: Message, state: FSMContext) -> None:
    """Обработка введённого тега игрока Brawl Stars."""
    player_tag = message.text.strip().upper()
    if not player_tag.startswith("#"):
        player_tag = "#" + player_tag

    # Проверка защиты от мультиаккаунтов
    existing_user = await queries.get_user_by_player_tag(player_tag)
    if existing_user:
        await message.answer(
            "❌ Этот аккаунт Brawl Stars уже привязан к другому пользователю.\n\n"
            "Регистрация запрещена. Пожалуйста, введите другой тег:",
            reply_markup=cancel_keyboard()
        )
        return

    checking_msg = await message.answer("⏳ Проверяем существование игрока и членство в клубе...")

    client = BrawlStarsClient()
    try:
        player_data = await client.get_player(player_tag)
        if not player_data:
            await checking_msg.edit_text(
                "❌ Игрок с таким тегом не найден в Brawl Stars.\n\n"
                "Проверьте правильность и введите тег ещё раз:",
                reply_markup=cancel_keyboard()
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

        if not in_allowed_club:
            await checking_msg.edit_text(
                "❌ Доступ к боту доступен только участникам официальных клубов системы.",
                reply_markup=cancel_keyboard()
            )
            await state.clear()
            return

        # Все проверки пройдены, завершаем регистрацию
        data = await state.get_data()
        nickname = data["nickname"]

        user = await queries.create_user(
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            nickname=nickname,
            player_tag=player_tag,
            club_name=club_name
        )

        await state.clear()
        logger.info(f"Новый пользователь зарегистрирован: {nickname} (TG: {message.from_user.id}, BS: {player_tag})")

        await checking_msg.delete()
        await message.answer(
            f"✅ <b>Регистрация прошла успешно!</b>\n\n"
            f"👤 Никнейм в боте: <b>{nickname}</b>\n"
            f"🏷️ Тег игрока Brawl Stars: <b>{player_tag}</b>\n"
            f"🏠 Название клуба: <b>{club_name or '—'}</b>\n\n"
            f"Добро пожаловать в систему!",
            parse_mode="HTML"
        )
        await show_main_menu(message, user)

    except BrawlStarsAPIError as e:
        await checking_msg.edit_text(
            f"❌ Ошибка Brawl Stars API: {e}\n\n"
            f"Попробуйте отправить тег ещё раз или обратитесь к администрации.",
            reply_markup=cancel_keyboard()
        )


@router.callback_query(F.data == "main_menu")
async def back_to_main(callback: CallbackQuery, state: FSMContext) -> None:
    """Возврат в главное меню."""
    await state.clear()
    user = await queries.get_user_by_telegram_id(callback.from_user.id)

    if not user:
        await callback.answer("Пожалуйста, зарегистрируйтесь через /start", show_alert=True)
        return

    if user.get("is_blocked"):
        await callback.answer("🚫 Ваш аккаунт заблокирован.", show_alert=True)
        return

    await show_main_menu(callback, user)


@router.callback_query(F.data == "cancel_form")
async def cancel_form(callback: CallbackQuery, state: FSMContext) -> None:
    """Отмена любой FSM-формы."""
    await state.clear()
    user = await queries.get_user_by_telegram_id(callback.from_user.id)

    if not user:
        await callback.message.edit_text(
            "Регистрация отменена. Нажмите /start для начала.",
            parse_mode="HTML"
        )
        await callback.answer()
        return

    await show_main_menu(callback, user)
