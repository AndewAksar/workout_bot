# bot/handlers/settings_command.py
"""
Модуль: settings_command.py
Описание: Модуль содержит обработчик команды /settings.

Зависимости:
- telegram: Для взаимодействия с Telegram API.
- telegram.ext: Для работы с контекстом и обновлениями Telegram.
- bot.keyboards.settings_menu: Для генерации меню настроек и подменю.

Автор: Aksarin A.
Дата создания: 19/08/2025
"""

from telegram import Update
from telegram.ext import ContextTypes

from bot.keyboards.settings_menu import get_settings_menu
from bot.utils.message_deletion import schedule_message_deletion
from bot.utils.logger import setup_logging


logger = setup_logging()

# Обработчик команды /settings
async def settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id
    chat_id = update.message.chat_id
    message_id = update.message.message_id

    try:
        await update.message.reply_text(
            "⚙️ Настройки профиля:",
            reply_markup=get_settings_menu()
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