# bot/handlers/start_command.py
"""
Модуль: start_command.py
Описание: Модуль содержит обработчик команды /start.

Зависимости:
- sqlite3: Для работы с базой данных SQLite.
- telegram: Для взаимодействия с Telegram API.
- telegram.ext: Для работы с контекстом и обновлениями Telegram.
- bot.config.settings: Для получения конфигурационных данных (WELCOME_MESSAGE).
- bot.keyboards.main_menu: Для генерации главного меню.
- bot.utils.message_deletion: Для планирования удаления сообщений.
"""

import sqlite3
import os

from telegram import Update
from telegram.ext import ContextTypes

from bot.config.settings import WELCOME_MESSAGE, DB_PATH
from bot.keyboards.main_menu import get_main_menu
from bot.utils.logger import setup_logging
from bot.utils.message_deletion import schedule_message_deletion


logger = setup_logging()

# Обработчик команды /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
        Обработчик команды /start.
        Описание:
            Выполняет начальную регистрацию пользователя или обновление его данных в базе данных.
            Извлекает информацию о пользователе (ID, имя, username) и сохраняет её.
            Формирует приветственное сообщение с данными профиля (если они есть) и отправляет его с главным меню.
            Планирует удаление команды /start через 3 секунды, оставляя ответное сообщение с меню.
        Аргументы:
            update (telegram.Update): Объект обновления, содержащий информацию о входящем сообщении.
            context (telegram.ext.ContextTypes.DEFAULT_TYPE): Контекст выполнения команды, предоставляющий доступ к данным бота.
        Возвращаемое значение:
            None
        Исключения:
            - sqlite3.Error: Если возникают ошибки при работе с базой данных.
            - telegram.error.TelegramError: Если возникают ошибки при отправке сообщения.
        Пример использования:
            Пользователь отправляет команду /start, бот отвечает приветственным сообщением и отображает главное меню.
            Сообщение с командой /start удаляется через 3 секунды, ответ бота с меню остается.
    """
    # Извлечение данных пользователя из объекта Update
    user = update.message.from_user
    user_id = user.id
    username = user.username if user.username else "друг"
    first_name = user.first_name if user.first_name else ""

    try:
        logger.info(f"Подключение к базе данных: {DB_PATH}, файл существует: {os.path.exists(DB_PATH)}")
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()

        # Проверка существования таблицы
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='UserSettings'")
        if not c.fetchone():
            logger.error("Таблица UserSettings не существует, вызываем init_db")
            from bot.database.db_init import init_db
            init_db()

        # Проверка, существует ли пользователь
        c.execute("SELECT name FROM UserSettings WHERE user_id = ?", (user_id,))
        existing_user = c.fetchone()

        if not existing_user:
            # Создание новой записи для нового пользователя
            c.execute(
                "INSERT INTO UserSettings (user_id, username, name) VALUES (?, ?, ?)",
                (user_id, username, first_name)
            )
            logger.info(f"Создана новая запись для пользователя {user_id} (@{username})")
        else:
            # Обновление только username для существующего пользователя
            c.execute(
                "UPDATE UserSettings SET username = ? WHERE user_id = ?",
                (username, user_id)
            )
            logger.info(f"Обновлены данные username для пользователя {user_id} (@{username})")

        conn.commit()

        # Получение данных профиля
        c.execute(
            "SELECT name, age, weight, height, gender FROM UserSettings WHERE user_id = ?",
            (user_id,)
        )
        profile = c.fetchone()

        # Формирование приветственного сообщения
        greeting = (
            f"<b>Привет, {profile[0] or username}! 👋</b>\n"
            f"Твой ID: <code>{user_id}</code>\n"
        )
        # Проверка наличия дополнительных данных профиля
        if profile and any(profile[1:]):
            greeting += (
                f"\n📋 <b>Твой профиль:</b>\n"
                f"Возраст: {profile[1] if profile[1] else 'Не указан'}\n"
                f"Вес: {profile[2] if profile[2] else 'Не указан'} кг\n"
                f"Рост: {profile[3] if profile[3] else 'Не указан'} см\n"
                f"Пол: {profile[4] if profile[4] else 'Не указан'}\n"
            )
        greeting += f"{WELCOME_MESSAGE}"

        # Отправка приветственного сообщения с главным меню
        await update.message.reply_text(
            greeting,
            parse_mode="HTML",
            reply_markup=get_main_menu()
        )

        # Планируем удаление только сообщения с командой /start
        await schedule_message_deletion(
            context,
            [update.message.message_id],
            chat_id=update.message.chat_id,
            delay=5
        )

    except sqlite3.Error as e:
        logger.error(f"Ошибка базы данных для пользователя {user_id}: {e}")
        sent_message = await update.message.reply_text(
            "❌ Произошла ошибка при создании профиля. Попробуйте снова.",
            reply_markup=get_main_menu()
        )

        # Планируем удаление только сообщения с командой /start даже при ошибке
        await schedule_message_deletion(
            context,
            [update.message.message_id],
            chat_id=update.message.chat_id,
            delay=5
        )

    except Exception as e:
        logger.error(f"Неожиданная ошибка для пользователя {user_id}: {e}")
        sent_message = await update.message.reply_text(
            "❌ Произошла непредвиденная ошибка. Попробуйте снова позже.",
            reply_markup=get_main_menu()
        )
        # Планируем удаление только сообщения с командой /start даже при ошибке
        await schedule_message_deletion(
            context,
            [update.message.message_id],
            chat_id=update.message.chat_id,
            delay=5
        )

    finally:
        if 'conn' in locals():
            conn.close()
            logger.info(f"Соединение с базой данных закрыто для пользователя {user_id}")

