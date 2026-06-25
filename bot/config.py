"""
Загрузка конфигурации из .env файла.
"""

import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    bot_token: str
    owner_id: int
    daily_request_limit: int
    database_path: str
    brawl_stars_api_token: str


def load_config() -> Config:
    bot_token = os.getenv("BOT_TOKEN")
    if not bot_token:
        raise ValueError("BOT_TOKEN не задан в .env файле!")

    owner_id = os.getenv("OWNER_ID")
    if not owner_id:
        raise ValueError("OWNER_ID не задан в .env файле!")

    return Config(
        bot_token=bot_token,
        owner_id=int(owner_id),
        daily_request_limit=int(os.getenv("DAILY_REQUEST_LIMIT", "3")),
        database_path=os.getenv("DATABASE_PATH", "bot/database/club_bot.db"),
        brawl_stars_api_token=os.getenv("BRAWL_STARS_API_TOKEN", ""),
    )


config = load_config()
