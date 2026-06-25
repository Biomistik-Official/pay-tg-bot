"""
Middleware для авторизации и проверки статуса блокировки пользователя.
"""

from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery

from bot.database import queries


class AuthBlockMiddleware(BaseMiddleware):
    """Проверяет статус блокировки пользователя перед обработкой любого события."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        user_id = None
        username = None
        
        if isinstance(event, Message) and event.from_user:
            user_id = event.from_user.id
            username = event.from_user.username
        elif isinstance(event, CallbackQuery) and event.from_user:
            user_id = event.from_user.id
            username = event.from_user.username

        if user_id:
            # Разрешаем команду /start беспрепятственно проходить, 
            # чтобы хэндлер мог показать стартовое приветствие или статус блока.
            if isinstance(event, Message) and event.text and event.text.startswith("/start"):
                return await handler(event, data)

            user = await queries.get_user_by_telegram_id(user_id)
            if user:
                # Обновляем username, если он изменился
                if user.get("username") != username:
                    await queries.update_username(user_id, username)

                is_blocked = user.get("is_blocked", 0)
                if is_blocked == 1:
                    # Ручная блокировка администратором
                    if isinstance(event, Message):
                        await event.answer("🚫 Ваш аккаунт заблокирован. Обратитесь к владельцу.")
                    elif isinstance(event, CallbackQuery):
                        await event.answer("🚫 Ваш аккаунт заблокирован.", show_alert=True)
                    return
                elif is_blocked == 2:
                    # Автоматическая блокировка за выход из разрешённого клуба
                    msg = (
                        "❌ <b>Ваш доступ временно отключён.</b>\n\n"
                        "Причина:\n"
                        "Вы больше не состоите в одном из клубов системы."
                    )
                    if isinstance(event, Message):
                        await event.answer(msg, parse_mode="HTML")
                    elif isinstance(event, CallbackQuery):
                        await event.answer(msg, show_alert=True)
                    return

        return await handler(event, data)
