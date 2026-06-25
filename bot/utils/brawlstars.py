"""
Клиент для взаимодействия с официальным Brawl Stars API.
"""

import aiohttp
from typing import Optional, Dict, Any
from bot.config import config
from bot.utils.logger import logger


class BrawlStarsAPIError(Exception):
    """Исключение при ошибках работы с Brawl Stars API."""
    pass


# Разрешенные клубы системы
ALLOWED_CLUBS = {
    "#2UUQ0989V": "ViGarik Squad",
    "#2CL9LRVCL": "ViGarik Academy",
    "#2CP8R2Q8U": "ViGarik Events"
}


class BrawlStarsClient:
    """Класс-клиент для работы с Brawl Stars API."""

    def __init__(self, token: Optional[str] = None):
        self.token = token or config.brawl_stars_api_token
        self.base_url = "https://api.brawlstars.com/v1"

    async def get_player(self, player_tag: str) -> Optional[Dict[str, Any]]:
        """
        Получить данные игрока из Brawl Stars API.
        
        :param player_tag: Тег игрока (например, #2UUQ0989V)
        :return: Словарь с данными игрока или None, если игрок не найден.
        """
        if not self.token:
            logger.error("Brawl Stars API токен не настроен в конфигурации (BRAWL_STARS_API_TOKEN)!")
            raise BrawlStarsAPIError("Brawl Stars API токен не настроен!")

        # Нормализуем тег
        tag = player_tag.strip().upper()
        if not tag.startswith("#"):
            tag = "#" + tag

        # URL-кодирование тега (символ # заменяется на %23)
        encoded_tag = tag.replace("#", "%23")
        url = f"{self.base_url}/players/{encoded_tag}"
        
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json"
        }

        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url, headers=headers, timeout=10) as response:
                    if response.status == 200:
                        return await response.json()
                    elif response.status == 404:
                        logger.info(f"Игрок с тегом {tag} не найден в Brawl Stars (404).")
                        return None
                    elif response.status == 403:
                        logger.error("Brawl Stars API вернул 403 Forbidden. Неверный токен или не разрешён IP.")
                        raise BrawlStarsAPIError("Неверный токен API или IP-адрес не добавлен в разрешенные на портале.")
                    else:
                        text = await response.text()
                        logger.error(f"Неизвестная ошибка Brawl Stars API: {response.status} - {text}")
                        raise BrawlStarsAPIError(f"Ошибка API Brawl Stars (статус {response.status})")
            except aiohttp.ClientError as e:
                logger.error(f"Сетевая ошибка при запросе к Brawl Stars API: {e}")
                raise BrawlStarsAPIError("Не удалось связаться с сервером Brawl Stars.")
