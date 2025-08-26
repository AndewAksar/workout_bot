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

Автор: Aksarin A.
Дата создания: 19/08/2025
"""

import sqlite3
from telegram import Update
from telegram.ext import (
    ContextTypes,
    ConversationHandler
)

from bot.keyboards.main_menu import get_main_menu
from bot.keyboards.settings_menu import get_settings_menu
from bot.keyboards.personal_data_menu import get_personal_data_menu
from bot.keyboards.training_settings_menu import get_training_settings_menu
from bot.keyboards.ai_assistant_menu import get_ai_assistant_menu
from bot.utils.logger import setup_logging
from bot.config.settings import (
    DB_PATH,
    SET_NAME,
    SET_AGE,
    SET_WEIGHT,
    SET_HEIGHT,
    SET_GENDER
)
from bot.ai_assistant.ai_handler import (
    start_ai_assistant, end_ai_consultation
)

# Инициализация логгера для записи событий и ошибок.
logger = setup_logging()

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обработчик callback-запросов для интерактивных кнопок.
    Описание:
        Обрабатывает нажатия на кнопки в меню, выполняет соответствующие действия
        (например, отображение меню, профиля или запуск ввода данных) и возвращает
        состояние ConversationHandler для продолжения диалога или его завершения.
    Аргументы:
        update (telegram.Update): Объект обновления, содержащий информацию о callback-запросе.
        context (telegram.ext.ContextTypes.DEFAULT_TYPE): Контекст выполнения команды.
    Возвращаемое значение:
        int: Состояние ConversationHandler (например, SET_NAME, SET_AGE или ConversationHandler.END).
    Исключения:
        - sqlite3.Error: Если возникают ошибки при работе с базой данных.
        - telegram.error.TelegramError: Если возникают ошибки при отправке сообщений.
    Пример использования:
        Пользователь нажимает кнопку в меню, бот отвечает соответствующим сообщением и/или переходит
        в состояние ввода данных.
    """

    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    logger.info(f"Пользователь {user_id} нажал кнопку: {query.data}")

    # Подключение к базе данных
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    if query.data == "start_training":
        await query.message.edit_text(
            "🏋️‍♂️ Тренировка начата! Следуйте инструкциям или добавьте свои упражнения.",
            reply_markup=get_main_menu()
        )
    elif query.data == "my_trainings":
        await query.message.edit_text(
            "🗂️ Здесь будут отображаться ваши тренировки (функция в разработке).",
            reply_markup=get_main_menu()
        )
    elif query.data == "my_ai_assistant":
        await query.message.edit_text(
            "🤖 Воспользоваться AI-консультантом.",
            reply_markup=get_ai_assistant_menu()
        )

    elif query.data == "start_ai_assistant":
        return await start_ai_assistant(update, context)

    elif query.data == "end_ai_consultation":
        return await end_ai_consultation(update, context)

    elif query.data == "settings":
        await query.message.edit_text(
            "⚙️ Настройки профиля:",
            reply_markup=get_settings_menu()
        )
    elif query.data == "personal_data":
        await query.message.edit_text(
            "📋 Выберите, что хотите изменить:",
            reply_markup=get_personal_data_menu()
        )
    elif query.data == "training_settings":
        await query.message.edit_text(
            "🏋️ Настройки тренировок:",
            reply_markup=get_training_settings_menu()
        )
    elif query.data == "show_profile":
        c.execute("SELECT name, age, weight, height, gender, username "
                      "FROM UserSettings "
                      "WHERE user_id = ?",
                  (user_id,))
        profile = c.fetchone()
        if profile:
            greeting = (
                f"<b>Ваш профиль:</b>\n"
                f"👤 Имя: <code>{profile[0] if profile[0] else 'Не указано'}</code>\n"
                f"Возраст: <code>{profile[1] if profile[1] else 'Не указан'}</code>\n"
                f"Вес: <code>{profile[2] if profile[2] else 'Не указан'}</code> кг\n"
                f"Рост: <code>{profile[3] if profile[3] else 'Не указан'}</code> см\n"
                f"Пол: <code>{profile[4] if profile[4] else 'Не указан'}</code>\n\n"
                f"📧 Telegram: <code>@{profile[5] if profile[5] else 'Не указан'}</code>"
            )
        else:
            greeting = "⚠️ Профиль не найден. Пожалуйста, используйте /start для инициализации."
        await query.message.edit_text(
            greeting,
            parse_mode="HTML",
            reply_markup=get_settings_menu()
        )

    elif query.data == "main_menu":
        await query.message.edit_text(
            "💪 Выберите действие в меню ниже:",
            reply_markup=get_main_menu()
        )

    elif query.data == "set_name":
        await query.message.edit_text(
            "✍️ Введите ваше имя:",
            reply_markup=None
        )

        logger.info(f"Переход в состояние SET_NAME для пользователя {user_id}")
        return SET_NAME

    elif query.data == "set_age":
        await query.message.edit_text(
            "✍️ Введите ваш возраст (число):",
            reply_markup=None
        )
        return SET_AGE
    elif query.data == "set_weight":
        await query.message.edit_text(
            "✍️️ Введите ваш вес в кг (например, 70.5):",
            reply_markup=None
        )
        return SET_WEIGHT
    elif query.data == "set_height":
        await query.message.edit_text(
            "✍️ Введите ваш рост в см (например, 175):",
            reply_markup=None
        )

        return SET_HEIGHT
    elif query.data == "set_gender":
        await query.message.edit_text(
            "✍️ Введите ваш пол (мужской/женский):",
            reply_markup=None
        )

        return SET_GENDER

    conn.close()
    return ConversationHandler.END