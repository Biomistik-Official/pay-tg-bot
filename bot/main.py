"""
Точка входа — запуск бота.
"""

import asyncio
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from bot.config import config
from bot.database.models import init_db
from bot.middlewares.throttling import ThrottlingMiddleware
from bot.middlewares.auth import AuthBlockMiddleware
from bot.utils.logger import logger
from bot.utils.sync import auto_sync_clubs

# Импорт роутеров
from bot.handlers import start, profile, currency, requests, history, shop, staff_quests
from bot.handlers.admin import panel, users, tickets, points, requests as admin_requests, stats, shop_admin, staff, announcements, quests, club_activity as admin_club_activity


async def main() -> None:
    """Основная функция запуска бота."""

    # Инициализация БД
    logger.info("Инициализация базы данных...")
    await init_db()
    logger.info("База данных готова.")

    # Создание бота и диспетчера
    bot = Bot(
        token=config.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher(storage=MemoryStorage())

    # Подключение throttling middleware
    dp.message.middleware(ThrottlingMiddleware(rate_limit=1.0))

    # Подключение middleware блокировки и авторизации
    block_middleware = AuthBlockMiddleware()
    dp.message.outer_middleware(block_middleware)
    dp.callback_query.outer_middleware(block_middleware)

    # Подключение роутеров (порядок важен!)
    dp.include_router(start.router)
    dp.include_router(profile.router)
    dp.include_router(currency.router)
    dp.include_router(requests.router)
    dp.include_router(history.router)

    # Админ роутеры
    dp.include_router(panel.router)
    dp.include_router(users.router)
    dp.include_router(tickets.router)
    dp.include_router(points.router)
    dp.include_router(admin_requests.router)
    dp.include_router(stats.router)
    dp.include_router(shop_admin.router)
    dp.include_router(shop.router)
    dp.include_router(staff.router)
    dp.include_router(announcements.router)
    dp.include_router(quests.router)
    dp.include_router(admin_club_activity.router)

    # Роутер для Staff
    dp.include_router(staff_quests.router)

    # Запуск поллинга и фоновых задач
    logger.info(f"Бот запущен. Owner ID: {config.owner_id}")
    logger.info(f"Лимит заявок в день: {config.daily_request_limit}")

    # Создаем фоновую задачу автосинхронизации и удерживаем ссылку на нее
    background_tasks = set()
    sync_task = asyncio.create_task(auto_sync_clubs(bot))
    background_tasks.add(sync_task)
    sync_task.add_done_callback(background_tasks.discard)

    try:
        # Сбрасываем все накопившиеся за время офлайна старые обновления
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()
        logger.info("Бот остановлен.")


if __name__ == "__main__":
    asyncio.run(main())
