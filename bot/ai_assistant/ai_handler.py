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
    ConversationHandler
)

from bot.utils.logger import setup_logging
from bot.keyboards.main_menu import get_main_menu
from bot.ai_assistant.ai_api import generate_gigachat_response
from bot.utils.message_deletion import schedule_message_deletion


logger = setup_logging()

# Состояния для ConversationHandler
AI_CONSULTATION = 1

# Глобальная переменная для хранения токена
GIGACHAT_AUTH_TOKEN = None

# Ограничение на длину сообщения
MAX_MESSAGE_LENGTH = 4096

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

    # Устанавливаем флаг активного диалога
    context.user_data['conversation_active'] = True

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
    chat_id = update.effective_chat.id
    logger.info(f"Пользователь {user_id} спросил AI: {user_message}")

    try:
        response = generate_gigachat_response(user_message, user_id)
        logger.debug(f"Длина ответа от GigaChat: {len(response)} символов")

        # Разделяем ответ, если он превышает лимит Telegram
        if len(response) <= MAX_MESSAGE_LENGTH:
            sent_message = await update.message.reply_text(response)
        else:
            # Разбиваем текст на части по MAX_MESSAGE_LENGTH
            messages = []
            for i in range(0, len(response), MAX_MESSAGE_LENGTH):
                part = response[i:i + MAX_MESSAGE_LENGTH]
                # Убедимся, что часть заканчивается на полном предложении, если возможно
                if i + MAX_MESSAGE_LENGTH < len(response):
                    last_period = part.rfind('.')
                    if last_period != -1:
                        part = part[:last_period + 1]
                sent_message = await update.message.reply_text(part)
                messages.append(sent_message.message_id)

        return AI_CONSULTATION  # Остаемся в состоянии для продолжения диалога
    except Exception as e:
        logger.error(f"Ошибка в handle_ai_message для пользователя {user_id}: {e}")
        await update.callback_query.message.reply_text("⚠️ Произошла ошибка. Консультация завершена.")

        # Сбрасываем флаг диалога
        context.user_data['conversation_active'] = False

        return ConversationHandler.END

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

    # Сбрасываем флаг диалога
    context.user_data['conversation_active'] = False

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
    chat_id = update.effective_chat.id

    if update.callback_query:
        try:
            message = await update.callback_query.message.reply_text("⚠️ Произошла ошибка. Консультация завершена.")
            await schedule_message_deletion(context, [message.message_id], chat_id, delay=5)
        except Exception as send_error:
            logger.error(f"Ошибка при отправке сообщения об ошибке: {send_error}")

    elif update.message:
        try:
            message = await update.message.reply_text("⚠️ Произошла ошибка (2). Консультация завершена.")
            await schedule_message_deletion(context, [message.message_id], chat_id, delay=5)
        except Exception as send_error:
            logger.error(f"Ошибка при отправке сообщения об ошибке в чате {chat_id}: {send_error}")

    return ConversationHandler.END


