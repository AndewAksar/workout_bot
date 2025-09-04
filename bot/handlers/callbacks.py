# bot/handlers/callbacks.py
"""
Модуль: callbacks.py
Описание: Модуль содержит обработчики callback-запросов и состояний ConversationHandler
для Telegram-бота. Обрабатывает нажатия на интерактивные кнопки и обновление пользовательских
данных в базе данных SQLite. Также включает логирование действий пользователей.

Зависимости:
- sqlite3: Для работы с базой данных SQLite.
- telegram: Для взаимодействия с Telegram API.
- telegram.ext: Для работы с контекстом, обработчиками и ConversationHandler.
- bot.keyboards.main_menu: Для получения клавиатур меню.
- bot.utils.logger: Для настройки логирования.
"""

from telegram import Update
from telegram.ext import ContextTypes

from bot.utils.logger import setup_logging
from bot.config.settings import (
     SET_NAME,
     SET_AGE,
     SET_WEIGHT,
     SET_HEIGHT,
     SET_GENDER
)
from bot.utils.message_deletion import schedule_message_deletion


# Инициализация логгера для записи событий и ошибок.
logger = setup_logging()

# Функции для перехода в состояния ввода данных
async def set_name_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Переход в состояние ввода имени."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    chat_id = query.message.chat_id
    logger.info(f"Переход в состояние SET_NAME для пользователя {user_id}")

    message = await query.message.edit_text(
        "✍️ Введите ваше имя:",
        reply_markup=None
    )
    context.user_data['conversation_active'] = True
    await schedule_message_deletion(context, [message.message_id], chat_id, delay=15)
    return SET_NAME

async def set_age_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Переход в состояние ввода возраста."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    chat_id = query.message.chat_id
    logger.info(f"Переход в состояние SET_AGE для пользователя {user_id}")

    message = await query.message.edit_text(
        "✍️ Введите ваш возраст (число):",
        reply_markup=None
    )

    context.user_data['conversation_active'] = True
    context.user_data['current_state'] = 'SET_AGE'

    await schedule_message_deletion(context, [message.message_id], chat_id, delay=15)
    return SET_AGE

async def set_weight_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Переход в состояние ввода веса."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    chat_id = query.message.chat_id
    logger.info(f"Переход в состояние SET_WEIGHT для пользователя {user_id}")

    message = await query.message.edit_text(
        "✍️️ Введите ваш вес в кг (например, 70.5):",
        reply_markup=None
    )
    context.user_data['conversation_active'] = True
    await schedule_message_deletion(context, [message.message_id], chat_id, delay=15)
    return SET_WEIGHT

async def set_height_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Переход в состояние ввода роста."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    chat_id = query.message.chat_id
    logger.info(f"Переход в состояние SET_HEIGHT для пользователя {user_id}")

    message = await query.message.edit_text(
        "✍️ Введите ваш рост в см (например, 175):",
        reply_markup=None
    )
    context.user_data['conversation_active'] = True
    await schedule_message_deletion(context, [message.message_id], chat_id, delay=15)
    return SET_HEIGHT

async def set_gender_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Переход в состояние ввода пола."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    chat_id = query.message.chat_id
    logger.info(f"Переход в состояние SET_GENDER для пользователя {user_id}")

    message = await query.message.edit_text(
        "✍️ Введите ваш пол (мужской/женский):",
        reply_markup=None
    )
    context.user_data['conversation_active'] = True
    await schedule_message_deletion(context, [message.message_id], chat_id, delay=15)
    return SET_GENDER