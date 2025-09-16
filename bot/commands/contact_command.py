# bot/handlers/contact_command.py
"""
Модуль: contact_command.py
Описание: Модуль содержит обработчик команды /contacts.

Зависимости:
- telegram: Для взаимодействия с Telegram API.
- telegram.ext: Для работы с контекстом и обновлениями Telegram.

Автор: Aksarin A.
Дата создания: 19/08/2025
"""

from telegram import Update
from telegram.ext import ContextTypes

from bot.utils.message_deletion import schedule_message_deletion
from bot.utils.logger import setup_logging


logger = setup_logging()

# Обработчик команды /contact
async def contact(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id
    chat_id = update.message.chat_id
    message_id = update.message.message_id

    try:
        logger.info(f"Команда /contacts вызвана пользователем {user_id} в чате {chat_id}")
        await update.message.reply_text(
            f"📞 <b>Контакты владельца:</b>\n"
            f"Телеграм: <a href='https://t.me/dedandrew'>@dedandrew</a>\n",
            parse_mode="HTML"
        )
        logger.info(f"Отправлен ответ на команду /contacts в чате {chat_id}")

        # Планируем удаление только сообщения с командой /сontacts
        schedule_message_deletion(
            context,
            [update.message.message_id],
            chat_id=update.message.chat_id,
            delay=5
        )
    except Exception as e:
        logger.error(f"Ошибка при обработке команды /contacts для пользователя {user_id}: {e}")
        await update.message.reply_text(
            "❌ Произошла ошибка при отправке контактов. Попробуйте снова позже.",
            parse_mode="HTML"
        )