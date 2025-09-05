# bot/handlers/help_command.py
"""
Модуль: help_command.py
Описание: Модуль содержит обработчик команды /help.
Обработчик используют клавиатуру для интерактивного интерфейса.

Зависимости:
- telegram: Для взаимодействия с Telegram API.
- telegram.ext: Для работы с контекстом и обновлениями Telegram.
- InlineKeyboardButton: Кнопка для клавиатуры.
- InlineKeyboardMarkup: Макет клавиатуры.

Автор: Aksarin A.
Дата создания: 19/08/2025
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
        keyboard = [
            [
                InlineKeyboardButton(
                    "🚀 Стартовать бота", callback_data='start'
                )
            ],
            [
                InlineKeyboardButton(
                    "⚙️ Настройки", callback_data='settings'
                )
            ],
            [
                InlineKeyboardButton(
                    "📞 Контакты владельца", callback_data='contacts'
                )
            ],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            "Выберите команду:",
            reply_markup=reply_markup
        )

        # Планируем удаление только сообщения с командой /contacts
        logger.info(f"Планируется удаление сообщения {message_id} в чате {chat_id}")
        await schedule_message_deletion(
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
