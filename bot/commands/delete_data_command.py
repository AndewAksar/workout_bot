# bot/commands/delete_data_command.py
"""
Модуль: delete_data_command.py.
Описание: Команда для удаления пользовательских данных.
Зависимости:
- aiosqlite - библиотека для асинхронной работы с SQLite.
- telegram - библиотека для работы с Telegram API.
- bot.config.settings - модуль с настройками базы данных.
- bot.utils.logger - модуль для логирования.
"""

import aiosqlite
from telegram import Update
from telegram.ext import ContextTypes

from bot.config.settings import DB_PATH
from bot.utils.logger import setup_logging


logger = setup_logging()

async def delete_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Удаляет данные пользователя из всех таблиц."""
    user_id = update.message.from_user.id
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
            await db.execute("DELETE FROM UserSettings WHERE user_id = ?", (user_id,))
            await db.commit()
        await update.message.reply_text("Ваши данные удалены в соответствии с GDPR.")
        logger.info(f"Данные пользователя {user_id} удалены")
    except aiosqlite.Error as e:
        logger.error(f"Ошибка при удалении данных пользователя {user_id}: {e}")
        await update.message.reply_text("Не удалось удалить данные. Попробуйте позже.")
