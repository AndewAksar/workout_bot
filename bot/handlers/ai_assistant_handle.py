# bot/handlers/ai_assistant_handle.py
"""
Модуль: ai_assistant.py
Описание: Модуль управляет запуском и завершением работы AI-ассистента Telegram-бота.
Зависимости:
- telegram: Для взаимодействия с Telegram API.
- telegram.ext: Для работы с контекстом и ConversationHandler.
- bot.keyboards.ai_assistant_menu: Для получения клавиатуры AI-ассистента.
- bot.ai_assistant.ai_handler: Для функций AI-ассистента.
- bot.utils.logger: Для настройки логирования.
"""

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from bot.keyboards.ai_assistant_menu import get_ai_assistant_menu
from bot.ai_assistant.ai_handler import start_ai_assistant, end_ai_consultation
from bot.utils.logger import setup_logging


logger = setup_logging()

async def handle_ai_assistant(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обрабатывает запрос на запуск AI-ассистента.
    Аргументы:
        update (telegram.Update): Объект обновления с информацией о callback-запросе.
        context (telegram.ext.ContextTypes.DEFAULT_TYPE): Контекст выполнения команды.
    Возвращаемое значение:
        int: Состояние ConversationHandler.
    """
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    logger.info(f"Пользователь {user_id} запросил AI-ассистента")

    await query.message.edit_text(
        "🤖 Воспользоваться AI-консультантом.",
        reply_markup=get_ai_assistant_menu()
    )
    # Передаем управление в start_ai_assistant для входа в AI_CONSULTATION
    return await start_ai_assistant(update, context)

async def start_ai(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Запускает AI-ассистента."""
    return await start_ai_assistant(update, context)

async def end_ai(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Завершает консультацию с AI-ассистентом."""
    return await end_ai_consultation(update, context)