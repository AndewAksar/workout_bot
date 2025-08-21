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


# Обработчик команды /contact
async def contact(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        f"📞 <b>Контакты владельца:</b>\n"
        f"Телеграм: <a href='https://t.me/dedandrew'>@dedandrew</a>\n",
        parse_mode="HTML"
    )