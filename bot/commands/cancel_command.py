# bot/handlers/cancel_command.py
"""
Модуль: cancel_command.py
Описание: Модуль содержит обработчик команды /cancel

Зависимости:
- telegram: Для взаимодействия с Telegram API.
- telegram.ext: Для работы с контекстом и обновлениями Telegram.
- bot.keyboards.settings_menu: Для генерации меню настроек и подменю.

Автор: Aksarin A.
Дата создания: 21/08/2025
"""

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from bot.keyboards.settings_menu import get_settings_menu


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обработчик команды /cancel.

    Описание:
        Отменяет текущий диалог и возвращает пользователя в меню настроек.

    Аргументы:
        update (telegram.Update): Объект обновления, содержащий команду /cancel.
        context (telegram.ext.ContextTypes.DEFAULT_TYPE): Контекст выполнения команды.

    Возвращаемое значение:
        int: ConversationHandler.END, завершающий диалог.

    Пример использования:
        Пользователь отправляет /cancel, бот завершает диалог и возвращает меню настроек.
    """
    await update.message.reply_text(
        "🔙 Действие отменено.",
        reply_markup=get_settings_menu()
    )
    return ConversationHandler.END