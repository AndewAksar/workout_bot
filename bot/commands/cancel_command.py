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
from bot.utils.message_deletion import schedule_message_deletion
from bot.utils.logger import setup_logging


logger = setup_logging()

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обработчик команды /cancel.
    Описание: Отменяет текущий диалог и возвращает пользователя в меню настроек.
    Аргументы:
        update (telegram.Update): Объект обновления, содержащий команду /cancel.
        context (telegram.ext.ContextTypes.DEFAULT_TYPE): Контекст выполнения команды.
    Возвращаемое значение:
        int: ConversationHandler.END, завершающий диалог.
    Пример использования:
        Пользователь отправляет /cancel, бот завершает диалог и возвращает меню настроек.
    """
    user_id = update.message.from_user.id
    chat_id = update.message.chat_id
    message_id = update.message.message_id

    try:
        await update.message.reply_text(
            "❌ Действие отменено.",
            reply_markup=get_settings_menu()
        )

        # Планируем удаление только сообщения с командой /cancel
        logger.info(f"Планируется удаление сообщения {message_id} в чате {chat_id}")
        await schedule_message_deletion(
            context,
            [message_id],
            chat_id=chat_id,
            delay=5
        )

        return ConversationHandler.END

    except Exception as e:
        logger.error(f"Ошибка при обработке команды /cancel: {e}")
        await update.message.reply_text(
            "❌ Произошла ошибка. Попробуйте снова позже.",
            parse_mode="HTML"
        )