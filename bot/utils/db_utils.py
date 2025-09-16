# bot/utils/db_utils.py
"""
Модуль: db_utils.py
Описание: Вспомогательные функции для работы с базой данных пользователей.
Зависимости:
- aiosqlite: Для асинхронного взаимодействия с базой данных.
- datetime: Для расчёта времени истечения токена.
- typing: Для аннотаций типов.
- bot.config.settings: Для получения пути к базе данных.
"""

import aiosqlite
from datetime import datetime, timedelta
from typing import Optional, Tuple

from bot.config.settings import DB_PATH
from bot.utils.logger import setup_logging


logger = setup_logging()

async def get_user_mode(user_id: int) -> str:
    """Возвращает режим работы пользователя."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT mode FROM users WHERE user_id = ?",
            (user_id,),
        ) as cursor:
            row = await cursor.fetchone()
    return row[0] if row else "local"


async def save_api_tokens(
    user_id: int,
    access_encrypted: str,
    refresh_encrypted: Optional[str],
    expires_in: int,
) -> None:
    """Сохраняет токены Gym-Stat в базе данных."""
    expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET api_token_encrypted = ?, refresh_token_encrypted = ?, token_expires_at = ? WHERE user_id = ?",
            (access_encrypted, refresh_encrypted, expires_at.isoformat(), user_id),
        )
        await db.commit()


async def get_api_tokens(user_id: int) -> Optional[Tuple[str, Optional[str], str]]:
    """Возвращает токены и время истечения."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT api_token_encrypted, refresh_token_encrypted, token_expires_at FROM users WHERE user_id = ?",
            (user_id,),
        ) as cursor:
            row = await cursor.fetchone()
        return row if row and row[0] and row[2] else None


async def clear_api_tokens(user_id: int) -> None:
    """Удаляет сохранённые токены Gym-Stat."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET api_token_encrypted = NULL, refresh_token_encrypted = NULL, token_expires_at = NULL WHERE user_id = ?",
            (user_id,),
        )
        await db.commit()