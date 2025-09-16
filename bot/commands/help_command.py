# bot/handlers/help_command.py
"""
Модуль: help_command.py
Описание: Модуль содержит обработчик команды /help.
Обработчик отправляет текстовое сообщение со списком доступных команд в виде ссылок.

Зависимости:
- telegram: Для взаимодействия с Telegram API.
- telegram.ext: Для работы с контекстом и обновлениями Telegram.
"""

from telegram import Update
from telegram.ext import ContextTypes
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup
)

from bot.utils.message_deletion import schedule_message_deletion
from bot.utils.logger import setup_logging


logger = setup_logging()

# Обработчик команды /help
async def help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id
    chat_id = update.message.chat_id
    message_id = update.message.message_id

    try:
        help_text = (
            "📋 Доступные команды:\n\n"
            "/start - Запустить бота\n"
            "/settings - Настройки\n"
            "/cancel - Отмена действия\n\n"
            "/login - Авторизация\n"
            "/logout - Выход\n"
            "/register - Регистрация\n\n"
            "/contacts - 📞 Контакты владельца"
        )

        await update.message.reply_text(
            help_text,
            parse_mode="HTML"
        )

        # Планируем удаление сообщения с командой /help
        logger.info(f"Планируется удаление сообщения {message_id} в чате {chat_id}")
        schedule_message_deletion(
            context,
            [message_id],
            chat_id=chat_id,
            delay=5
        )

    except Exception as e:
        logger.error(f"Ошибка при обработке команды /help: {e}")
        await update.message.reply_text(
            "❌ Произошла ошибка. Попробуйте снова позже.",
            parse_mode="HTML"

        )
