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


# Обработчик команды /settings
async def settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "⚙️ Настройки профиля:",
        reply_markup=get_settings_menu()
    )