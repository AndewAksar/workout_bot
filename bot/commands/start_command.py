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
from bot.keyboards.mode_selection import get_mode_selection_keyboard
from bot.utils.message_deletion import schedule_message_deletion


logger = setup_logging()

# Обработчик команды /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает команду /start."""
    # Извлечение данных пользователя из объекта Update
    user = update.message.from_user
    user_id = user.id
    username = user.username if user.username else "друг"
    first_name = user.first_name if user.first_name else ""

    try:
        logger.info(f"Подключение к базе данных: {DB_PATH}, файл существует: {os.path.exists(DB_PATH)}")
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()

        # Проверяем наличие таблиц
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        if not c.fetchone():
            from bot.database.db_init import init_db
            init_db()

        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='UserSettings'")

        if not c.fetchone():
            from bot.database.db_init import init_db
            init_db()

        # Проверяем, есть ли пользователь
        c.execute("SELECT mode FROM users WHERE user_id = ?", (user_id,))
        user_record = c.fetchone()

        if not user_record:
            c.execute(
            "INSERT INTO users (user_id, telegram_username, mode) VALUES (?, ?, 'local')",
            (user_id, username),
            )

        c.execute(
            "INSERT OR IGNORE INTO UserSettings (user_id, username, name) VALUES (?, ?, ?)",
            (user_id, username, first_name),
        )

        c.execute(
            "UPDATE UserSettings SET username = ?, name = COALESCE(name, ?) WHERE user_id = ?",
            (username, first_name, user_id),
        )

        c.execute(
            "UPDATE users SET telegram_username = ? WHERE user_id = ?",
            (username, user_id),
        )
        conn.commit()

        if not user_record:
            await update.message.reply_text(
                "💪 Добро пожаловать в бот для тренировок!\nВыберите режим работы:",
                reply_markup=get_mode_selection_keyboard()
            )
            await schedule_message_deletion(
                context,
                [update.message.message_id],
                chat_id=update.message.chat_id,
                delay=5)
            return

        c.execute("SELECT name, age, weight, height, gender FROM UserSettings WHERE user_id = ?", (user_id,))
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

