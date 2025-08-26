# bot/database/db_init.py
"""
Модуль: db_init.py
Описание: Модуль отвечает за инициализацию базы данных SQLite для хранения настроек пользователей Telegram-бота.
Создает таблицу UserSettings, если она еще не существует, для хранения пользовательских данных.

Зависимости:
- sqlite3: Для работы с базой данных SQLite.

Автор: Aksarin A.
Дата создания: 19/08/2025
"""

import sqlite3
import os
from bot.config.settings import DB_PATH
from bot.utils.logger import setup_logging


# Инициализация логгера
logger = setup_logging()

def init_db() -> None:
    """
    Инициализация базы данных SQLite.
    Описание:
        Создает подключение к базе данных 'users.db' и таблицу UserSettings, если она еще не существует.
        Таблица содержит поля для хранения пользовательских данных: user_id, name, age, weight, height,
        gender и username. После создания таблицы изменения фиксируются, и соединение закрывается.
    Аргументы: Нет
    Возвращаемое значение: None
    Исключения:
        - sqlite3.Error: Если возникают ошибки при подключении к базе данных или выполнении SQL-запроса.
    Пример использования:
        >>> init_db()
        [Создается база данных users.db с таблицей UserSettings, если она еще не существует]
    """
    try:
        # Используем абсолютный путь к базе данных
        logger.info(f"Инициализация базы данных по пути: {DB_PATH}, файл существует: {os.path.exists(DB_PATH)}")

        # Подключение к базе данных SQLite
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()

        # Создание таблицы UserSettings, если она не существует
        c.execute('''
                    CREATE TABLE IF NOT EXISTS UserSettings
                    (
                        user_id INTEGER PRIMARY KEY,
                        name TEXT,
                        age INTEGER,
                        weight REAL,
                        height REAL,
                        gender TEXT,
                        username TEXT
                    )
                ''')
        # Фиксация изменений в базе данных
        conn.commit()
        logger.info("Таблица UserSettings успешно создана или уже существует")
    except sqlite3.Error as e:
        logger.error(f"Ошибка при инициализации базы данных: e")
        raise

    finally:
        # Закрытие соединения с базой данных
        if conn:
            conn.close()
            logger.info("Соединение с базой данных закрыто")
