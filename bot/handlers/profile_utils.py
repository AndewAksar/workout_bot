# bot/handlers/profile_utils.py
"""
Модуль: profile_utils.py
Описание: Модуль содержит утилиты для работы с профилем пользователя в базе данных SQLite.
Предоставляет функции для сохранения начальных данных пользователя и получения данных профиля.

Зависимости:
- sqlite3: Для работы с базой данных SQLite.

Автор: Aksarin A.
Дата создания: 21/08/2025
"""

import sqlite3
from bot.utils.logger import setup_logging


# Инициализация логгера для записи событий и ошибок.
logger = setup_logging()

def save_user_data(user_id: int, username: str, name: str) -> None:
    """
    Сохранение или обновление данных пользователя в базе данных.
    Аргументы:
        user_id (целое число): Уникальный идентификатор пользователя
        username (строка): Имя пользователя
        name (строка): Имя пользователя
    """
    try:
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        logger.info(f"Попытка сохранить данные пользователя для user_id: {user_id}, username: {username}, name: {name}")

        c.execute(
            "INSERT OR REPLACE INTO UserSettings (user_id, username, name) VALUES (?, ?, ?)",
            (user_id, username, name)
        )
        conn.commit()
        logger.info(f"Данные пользователя успешно сохранены, user_id: {user_id}")

    except sqlite3.Error as e:
        logger.error(f"Ошибка базы данных при сохранении данных пользователя для user_id: {user_id}: {str(e)}")
        raise

    except Exception as e:
        logger.error(f"Ошибка при сохранении данных пользователя для user_id: {user_id}: {str(e)}")
        raise

    finally:
        if conn:
            conn.close()
            logger.debug("Соединение с базой данных закрыто")

def get_user_profile(user_id: int) -> tuple:
    """
    Извлечь профиль пользователя из базы данных.
    Аргументы: user_id (целое число): Уникальный идентификатор пользователя.
    Возвращает: кортеж: Данные профиля пользователя (имя, возраст, вес, рост, тип обучения, имя пользователя).
    """
    try:
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        logger.info(f"Попытка получить данные профиля пользователя для user_id: {user_id}")

        c.execute(
            "SELECT name, age, weight, height, training_type, username FROM UserSettings WHERE user_id = ?",
            (user_id,)
        )
        profile = c.fetchone()

        if profile:
            logger.info(f"Данные профиля пользователя успешно извлечены для user_id: {user_id}")
        else:
            logger.warning(f"Профиль не найден, user_id: {user_id}")

        return profile

    except sqlite3.Error as e:
        logger.error(f"Ошибка базы данных при получении данных профиля для user_id: {user_id}: {str(e)}")
        raise

    except Exception as e:
        logger.error(f"Ошибка при получении профиля пользователя для user_id: {user_id}: {str(e)}")
        raise

    finally:
        if conn:
            conn.close()
            logger.debug("Соединение с базой данных закрыто")