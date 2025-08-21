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


# Обработчик команды /help
async def help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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