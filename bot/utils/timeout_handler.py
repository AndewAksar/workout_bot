# bot/utils/timeout_handler.py
"""
Модуль для обработки таймаута: timeout_handler.py.
Описание:
Зависимости:
- telegram - библиотека для работы с Telegram API.
- bot.utils.logger - модуль для логирования.
- telegram.ext - библиотека для работы с расширенными контекстами.

"""

from telegram import Update
from bot.utils.logger import setup_logging
from telegram.ext import ContextTypes

from bot.keyboards.main_menu import get_main_menu


logger = setup_logging()

async def timeout_handler(context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обработчик таймаута для автоматического завершения режима ожидания ввода.
    Отправляет сообщение о таймауте и возвращает в главное меню.
    """
    job = context.job
    chat_id = job.data['chat_id']

    try:
        await context.bot.send_message(
            chat_id=chat_id,
            text="⏰ Время для ввода истекло. Возвращаемся в главное меню.",
            reply_markup=get_main_menu()
        )
        context.user_data['conversation_active'] = False
    except Exception as e:
        logger.error(f"Ошибка в timeout_handler для чата {chat_id}: {str(e)}")