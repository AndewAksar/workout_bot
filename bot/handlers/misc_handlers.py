# bot/handlers/misc_handlers.py
"""
Модуль: misc_handlers.py
Описание: Модуль содержит обработчики для прочих функций Telegram-бота, таких как начало тренировки,
отображение тренировок и переход в меню настроек.
Зависимости:
- telegram: Для взаимодействия с Telegram API.
- telegram.ext: Для работы с контекстом и ConversationHandler.
- bot.keyboards.main_menu: Для получения клавиатуры главного меню.
- bot.keyboards.settings_menu: Для получения клавиатуры настроек.
- bot.keyboards.personal_data_menu: Для получения клавиатуры персональных данных.
- bot.keyboards.training_settings_menu: Для получения клавиатуры настроек тренировок.
- bot.utils.logger: Для настройки логирования.
"""

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from bot.keyboards.main_menu import get_main_menu
from bot.keyboards.settings_menu import get_settings_menu
from bot.keyboards.personal_data_menu import get_personal_data_menu
from bot.keyboards.training_settings_menu import get_training_settings_menu
from bot.utils.logger import setup_logging


logger = setup_logging()

async def start_training(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает начало тренировки."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    logger.info(f"Пользователь {user_id} начал тренировку")

    await query.message.edit_text(
        "🏋️‍♂️ Тренировка начата! Следуйте инструкциям или добавьте свои упражнения.",
        reply_markup=get_main_menu()
    )
    context.user_data['conversation_active'] = False
    return ConversationHandler.END

async def show_trainings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отображает информацию о тренировках (функция в разработке)."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    logger.info(f"Пользователь {user_id} запросил список тренировок")

    await query.message.edit_text(
        "🗂️ Здесь будут отображаться ваши тренировки (функция в разработке).",
        reply_markup=get_main_menu()
    )
    context.user_data['conversation_active'] = False
    return ConversationHandler.END

async def show_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отображает меню настроек."""
    if update is None or update.callback_query is None:
        logger.error("Update or callback_query is None in show_settings")
        return ConversationHandler.END

    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    logger.info(f"Пользователь {user_id} открыл настройки")

    try:
        await query.message.edit_text(
            text="⚙️ Настройки профиля:",
            reply_markup=get_settings_menu()
        )
    except Exception as e:
        logger.error(f"Ошибка в show_settings для пользователя {user_id}: {e}")
        try:
            await query.message.reply_text(
                "⚠️ Произошла ошибка при открытии настроек. Попробуйте снова.",
                reply_markup=get_main_menu()
            )
        except Exception as reply_error:
            logger.error(f"Ошибка при отправке сообщения об ошибке для пользователя {user_id}: {reply_error}")
        return ConversationHandler.END

    context.user_data['conversation_active'] = False
    return ConversationHandler.END

async def show_personal_data_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отображает меню персональных данных."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    logger.info(f"Пользователь {user_id} открыл меню персональных данных")

    await query.message.edit_text(
        "📋 Выберите, что хотите изменить:",
        reply_markup=get_personal_data_menu()
    )
    context.user_data['conversation_active'] = False
    return ConversationHandler.END

async def show_training_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отображает меню настроек тренировок."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    logger.info(f"Пользователь {user_id} открыл настройки тренировок")

    await query.message.edit_text(
        "🏋️ Настройки тренировок:",
        reply_markup=get_training_settings_menu()
    )
    context.user_data['conversation_active'] = False
    return ConversationHandler.END

async def return_to_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Возвращает пользователя в главное меню."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    logger.info(f"Пользователь {user_id} вернулся в главное меню")

    await query.message.edit_text(
        "💪 Выберите действие в меню ниже:",
        reply_markup=get_main_menu()
    )
    context.user_data['conversation_active'] = False
    return ConversationHandler.END