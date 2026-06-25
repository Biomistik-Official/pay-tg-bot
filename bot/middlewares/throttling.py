"""
Throttling middleware — защита от спама.
"""

from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message
import time


class ThrottlingMiddleware(BaseMiddleware):
    """Ограничивает частоту сообщений: 1 запрос в секунду на пользователя."""

    def __init__(self, rate_limit: float = 1.0):
        self.rate_limit = rate_limit
        self._last_call: Dict[int, float] = {}

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        if isinstance(event, Message) and event.from_user:
            user_id = event.from_user.id
            now = time.monotonic()
            last = self._last_call.get(user_id, 0)

            if now - last < self.rate_limit:
                # Молча игнорируем слишком частые запросы
                return

            self._last_call[user_id] = now

        return await handler(event, data)
