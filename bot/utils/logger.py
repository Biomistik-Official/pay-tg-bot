"""
Утилита логирования.
"""

import logging
import os
from datetime import datetime

# Создаём папку для логов
os.makedirs("logs", exist_ok=True)

# Настройка формата
log_format = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
date_format = "%Y-%m-%d %H:%M:%S"

logging.basicConfig(
    level=logging.INFO,
    format=log_format,
    datefmt=date_format,
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(
            f"logs/bot_{datetime.now().strftime('%Y-%m-%d')}.log",
            encoding="utf-8"
        ),
    ]
)

# Отключаем лишний шум от aiogram
logging.getLogger("aiogram").setLevel(logging.WARNING)

logger = logging.getLogger("brawl_bot")


def log_admin_action(owner_id: int, action: str, details: str = "") -> None:
    """Логировать действие владельца."""
    logger.info(f"[OWNER:{owner_id}] {action} | {details}")
