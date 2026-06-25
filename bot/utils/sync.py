"""
Модуль фоновой синхронизации пользователей с Brawl Stars API.
"""

import asyncio
from aiogram import Bot
from bot.database import queries
from bot.utils.brawlstars import BrawlStarsClient, BrawlStarsAPIError, ALLOWED_CLUBS
from bot.utils.logger import logger


async def auto_sync_clubs(bot: Bot) -> None:
    """
    Фоновая задача для синхронизации клубов пользователей каждые 30 минут.
    
    Если игрок покинул один из разрешенных клубов — доступ блокируется.
    Если вернулся — доступ восстанавливается.
    Все данные профиля, балансы и история сохраняются.
    """
    client = BrawlStarsClient()
    
    # Небольшая пауза после старта бота, чтобы не мешать инициализации
    await asyncio.sleep(10)
    
    while True:
        logger.info("Запуск автоматической синхронизации участников клубов...")
        try:
            users = await queries.get_all_users()
            for user in users:
                telegram_id = user["telegram_id"]
                player_tag = user.get("player_tag")
                is_blocked = user.get("is_blocked", 0)
                
                # Пропускаем пользователей без привязанного тега
                if not player_tag:
                    continue
                
                try:
                    player_data = await client.get_player(player_tag)
                    if player_data is None:
                        logger.warning(
                            f"Игрок с тегом {player_tag} (TG: {telegram_id}) "
                            f"не найден в API при синхронизации."
                        )
                        continue
                    
                    club = player_data.get("club") or {}
                    club_tag = club.get("tag")
                    club_name = club.get("name")
                    
                    # Проверяем членство в разрешенных клубах
                    in_allowed_club = False
                    if club_tag:
                        norm_club_tag = club_tag.strip().upper()
                        if norm_club_tag in ALLOWED_CLUBS:
                            in_allowed_club = True
                    
                    # Обновляем название клуба в БД, если оно изменилось
                    if club_name != user.get("club_name"):
                        await queries.update_user_club_name(telegram_id, club_name)
                    
                    if in_allowed_club:
                        # Если пользователь был заблокирован автоматически (is_blocked == 2) — восстанавливаем доступ
                        if is_blocked == 2:
                            await queries.set_user_blocked(telegram_id, 0)
                            try:
                                await bot.send_message(
                                    telegram_id,
                                    "✅ <b>Доступ восстановлен.</b>\n\nДобро пожаловать обратно.",
                                    parse_mode="HTML"
                                )
                                logger.info(f"Доступ автоматически восстановлен для TG:{telegram_id} ({player_tag})")
                            except Exception as e:
                                logger.error(f"Не удалось отправить уведомление о разблокировке TG:{telegram_id}: {e}")
                    else:
                        # Если не состоит в разрешенных клубах и активен (is_blocked == 0) — блокируем доступ
                        if is_blocked == 0:
                            await queries.set_user_blocked(telegram_id, 2)
                            try:
                                await bot.send_message(
                                    telegram_id,
                                    "❌ <b>Ваш доступ временно отключён.</b>\n\n"
                                    "Причина:\n"
                                    "Вы больше не состоите в одном из клубов системы.",
                                    parse_mode="HTML"
                                )
                                logger.info(f"Доступ автоматически временно заблокирован для TG:{telegram_id} ({player_tag})")
                            except Exception as e:
                                logger.error(f"Не удалось отправить уведомление о блокировке TG:{telegram_id}: {e}")
                                
                except BrawlStarsAPIError as e:
                    logger.error(f"Ошибка Brawl Stars API при проверке TG:{telegram_id} ({player_tag}): {e}")
                except Exception as e:
                    logger.error(f"Непредвиденная ошибка при проверке TG:{telegram_id} ({player_tag}): {e}")
                
                # Задержка 1 секунда между пользователями для предотвращения превышения лимитов API
                await asyncio.sleep(1.0)
                
        except Exception as e:
            logger.error(f"Критическая ошибка в цикле автосинхронизации: {e}")
            
        # Запуск каждые 30 минут (1800 секунд)
        await asyncio.sleep(1800)
