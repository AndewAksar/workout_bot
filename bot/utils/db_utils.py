# bot/utils/db_utils.py
"""
Модуль: db_utils.py
Описание: Вспомогательные функции для работы с базой данных пользователей.
Зависимости:
- sqlite3: Для взаимодействия с базой данных.
- datetime: Для расчёта времени истечения токена.
- typing: Для аннотаций типов.
- bot.config.settings: Для получения пути к базе данных.
"""

import sqlite3
from datetime import datetime, timedelta
from typing import Optional, Tuple

from bot.config.settings import DB_PATH
from bot.utils.logger import setup_logging


logger = setup_logging()

def get_user_mode(user_id: int) -> str:
    """Возвращает режим работы пользователя."""
    conn = sqlite3.connect(DB_PATH)
    try:
        c = conn.cursor()
        c.execute("SELECT mode FROM users WHERE user_id = ?", (user_id,))
        row = c.fetchone()
        return row[0] if row else "local"
    finally:
        conn.close()


def save_api_tokens(
    user_id: int,
    access_encrypted: str,
    refresh_encrypted: Optional[str],
    expires_in: int,
) -> None:
    """Сохраняет токены Gym-Stat в базе данных."""
    expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
    conn = sqlite3.connect(DB_PATH)
    try:
        c = conn.cursor()
        c.execute(
            "UPDATE users SET api_token_encrypted = ?, refresh_token_encrypted = ?, token_expires_at = ? WHERE user_id = ?",
            (access_encrypted, refresh_encrypted, expires_at.isoformat(), user_id),
        )
        conn.commit()
    finally:
        conn.close()


def get_api_tokens(user_id: int) -> Optional[Tuple[str, Optional[str], str]]:
    """Возвращает токены и время истечения."""
    conn = sqlite3.connect(DB_PATH)
    try:
        c = conn.cursor()
        c.execute(
            "SELECT api_token_encrypted, refresh_token_encrypted, token_expires_at FROM users WHERE user_id = ?",
            (user_id,),
        )
        row = c.fetchone()
        return row if row and row[0] and row[2] else None
    finally:
        conn.close()


def clear_api_tokens(user_id: int) -> None:
    """Удаляет сохранённые токены Gym-Stat."""
    conn = sqlite3.connect(DB_PATH)
    try:
        c = conn.cursor()
        c.execute(
            "UPDATE users SET api_token_encrypted = NULL, refresh_token_encrypted = NULL, token_expires_at = NULL WHERE user_id = ?",
            (user_id,),
        )
        conn.commit()
    finally:
        conn.close()