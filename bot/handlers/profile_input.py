# bot/handlers/profile_input.py
"""
Модуль: profile_input.py
Описание: Модуль обрабатывает ввод данных профиля пользователя (имя, возраст, вес, рост, пол).
Зависимости:
- telegram: Для взаимодействия с Telegram API.
- telegram.ext: Для работы с контекстом и ConversationHandler.
- bot.utils.logger: Для настройки логирования.
- bot.config.settings: Для доступа к константам конфигурации.
"""

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from bot.utils.logger import setup_logging
from bot.config.settings import (
    SET_NAME,
    SET_AGE,
    SET_WEIGHT,
    SET_HEIGHT,
    SET_GENDER
)


logger = setup_logging()

async def set_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Запрашивает ввод имени пользователя."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    logger.info(f"Переход в состояние SET_NAME для пользователя {user_id}")

    await query.message.edit_text(
        "✍️ Введите ваше имя:",
        reply_markup=None
    )
    context.user_data['conversation_active'] = True
    return SET_NAME

async def set_age(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Запрашивает ввод возраста пользователя."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    logger.info(f"Переход в состояние SET_AGE для пользователя {user_id}")

    await query.message.edit_text(
        "✍️ Введите ваш возраст (число):",
        reply_markup=None
    )
    context.user_data['conversation_active'] = True
    return SET_AGE

async def set_weight(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Запрашивает ввод веса пользователя."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    logger.info(f"Переход в состояние SET_WEIGHT для пользователя {user_id}")

    await query.message.edit_text(
        "✍️️ Введите ваш вес в кг (например, 70.5):",
        reply_markup=None
    )
    context.user_data['conversation_active'] = True
    return SET_WEIGHT

async def set_height(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Запрашивает ввод роста пользователя."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    logger.info(f"Переход в состояние SET_HEIGHT для пользователя {user_id}")

    await query.message.edit_text(
        "✍️ Введите ваш рост в см (например, 175):",
        reply_markup=None
    )
    context.user_data['conversation_active'] = True
    return SET_HEIGHT

async def set_gender(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Запрашивает ввод пола пользователя."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    logger.info(f"Переход в состояние SET_GENDER для пользователя {user_id}")

    await query.message.edit_text(
        "✍️ Введите ваш пол (мужской/женский):",
        reply_markup=None
    )
    context.user_data['conversation_active'] = True
    return SET_GENDER