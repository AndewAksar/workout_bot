# bot/handlers/ai_handler.py
"""
Модуль: ai_handler.py
Описание: Модуль содержит обработчики для взаимодействия с AI-ассистентом в Telegram-боте.
Обеспечивает запуск, обработку сообщений и завершение консультации с AI через ConversationHandler.

Зависимости:
- telegram: Для взаимодействия с Telegram API.
- telegram.ext: Для работы с контекстом, обработчиками и ConversationHandler.
- bot.utils.logger: Для настройки логирования.
- bot.keyboards.main_menu: Для получения клавиатуры главного меню.
- bot.handlers.ai_api: Для взаимодействия с API GigaChat.

Автор: Aksarin A.
Дата создания: 26/08/2025
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters
)

from bot.utils.logger import setup_logging
from bot.keyboards.main_menu import get_main_menu
from bot.ai_assistant.ai_api import generate_gigachat_response


logger = setup_logging()

# Состояния для ConversationHandler
AI_CONSULTATION = 1

# Глобальная переменная для хранения токена
GIGACHAT_AUTH_TOKEN = None

# Обработчик запуска консультации с AI (вызывается по callback_data='start_ai_assistant')
async def start_ai_assistant(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обработчик для запуска консультации с AI-ассистентом.
    Аргументы:
        update (telegram.Update): Объект обновления Telegram.
        context (telegram.ext.ContextTypes.DEFAULT_TYPE): Контекст выполнения.
    Возвращаемое значение:
        int: Состояние AI_CONSULTATION для ConversationHandler.
    """
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    logger.info(f"Пользователь {user_id} начал консультацию с AI-ассистентом.")

    # Клавиатура с кнопкой выхода
    exit_keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🚪 Завершить консультацию", callback_data='end_ai_consultation')]
    ])

    await query.message.edit_text(
        "🤖 AI-консультант готов! Задайте свой вопрос по тренировкам, питанию или мотивации.\n\n"
        "Чтобы завершить, нажмите кнопку ниже.",
        reply_markup=exit_keyboard
    )
    return AI_CONSULTATION

# Обработчик сообщений во время консультации
async def handle_ai_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обработчик текстовых сообщений во время консультации с AI.
    Аргументы:
        update (telegram.Update): Объект обновления Telegram.
        context (telegram.ext.ContextTypes.DEFAULT_TYPE): Контекст выполнения.
    Возвращаемое значение:
        int: Состояние AI_CONSULTATION для продолжения диалога.
    """
    user_message = update.message.text
    user_id = update.effective_user.id
    logger.info(f"Пользователь {user_id} спросил AI: {user_message}")

    response = generate_gigachat_response(user_message, user_id)
    await update.message.reply_text(response)
    return AI_CONSULTATION  # Остаемся в состоянии для продолжения диалога

# Обработчик завершения консультации (по callback_data='end_ai_consultation')
async def end_ai_consultation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обработчик завершения консультации с AI.
    Аргументы:
        update (telegram.Update): Объект обновления Telegram.
        context (telegram.ext.ContextTypes.DEFAULT_TYPE): Контекст выполнения.
    Возвращаемое значение:
        int: ConversationHandler.END для завершения диалога.
    """
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    logger.info(f"Пользователь {user_id} завершил консультацию с AI-ассистентом.")

    await query.message.edit_text(
        "🤖 Консультация завершена. Возвращаемся в главное меню.",
        reply_markup=get_main_menu()
    )
    return ConversationHandler.END

# Обработчик ошибок для AI
async def ai_error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обработчик ошибок для AI-ассистента.
    Аргументы:
        update (telegram.Update): Объект обновления Telegram.
        context (telegram.ext.ContextTypes.DEFAULT_TYPE): Контекст выполнения.
    Возвращаемое значение:
        None
    """
    logger.error(f"Ошибка в AI-ассистенте: {context.error}")
    if update.callback_query:
        await update.callback_query.message.reply_text("⚠️ Произошла ошибка. Консультация завершена.")
    elif update.message:
        await update.message.reply_text("⚠️ Произошла ошибка. Консультация завершена.")
    return ConversationHandler.END