# bot/handlers/set_age.py
"""
Модуль: set_age.py
Описание: Модуль содержит обработчики для ввода данных профиля пользователя в рамках ConversationHandler
и определения состояний для диалогов. Обрабатывает ввод возраста и команду отмены.

Зависимости:
- aiosqlite: Для асинхронной работы с базой данных SQLite.
- telegram: Для взаимодействия с Telegram API.
- telegram.ext: Для работы с контекстом, обработчиками и ConversationHandler.
- bot.keyboards.personal_data_menu: Для получения меню личных данных.
- bot.keyboards.training_settings_menu: Для получения меню настроек тренировок.
- bot.keyboards.settings_menu: Для получения меню настроек.
- bot.utils.message_deletion: Для планирования удаления сообщений.
- bot.utils.logger: Для настройки логирования.
"""

import aiosqlite
from telegram import Update
from telegram.ext import (
    ContextTypes,
    ConversationHandler
)

from bot.keyboards.personal_data_menu import get_personal_data_menu
from bot.utils.logger import setup_logging
from bot.utils.message_deletion import schedule_message_deletion
from bot.config.settings import DB_PATH


logger = setup_logging()

async def set_age(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обработчик ввода возраста пользователя.
    Описание:
        Проверяет корректность введенного возраста (целое число от 0 до 150),
        сохраняет его в базе данных и возвращает меню личных данных.
        При некорректном вводе отправляет сообщение об ошибке.
    Аргументы:
        update (telegram.Update): Объект обновления, содержащий введенное сообщение.
        context (telegram.ext.ContextTypes.DEFAULT_TYPE): Контекст выполнения команды.
    Возвращаемое значение:
        int: ConversationHandler.END, завершающий диалог.
    Исключения:
        - ValueError: Если введено некорректное значение возраста.
        - aiosqlite.Error: Если возникают ошибки при работе с базой данных.
        - telegram.error.TelegramError: Если возникают ошибки при отправке сообщения.
    Пример использования:
        Пользователь вводит возраст, бот сохраняет его или запрашивает корректный ввод,
        отправляет подтверждение и планирует удаление сообщения пользователя.
    """
    user_id = update.message.from_user.id
    chat_id = update.message.chat_id
    user_message_id = update.message.message_id
    age = int(update.message.text.strip())

    logger.info(f"Начало обработки ввода имени для пользователя {user_id}: {age}")

    # Проверяем, что бот находится в состоянии SET_AGE
    if context.user_data.get('current_state') != 'SET_AGE':
        logger.warning(f"Некорректное состояние для set_age: {context.user_data.get('current_state')}")
        await update.message.reply_text(
            "⚠️ Пожалуйста, используйте команду для изменения возраста через меню настроек.",
            reply_markup=get_personal_data_menu()
        )
        return ConversationHandler.END

    try:
        if age < 0 or age > 150:
            raise ValueError("Некорректный возраст")
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "UPDATE UserSettings SET age = ? WHERE user_id = ?",
                (age, user_id),
            )
            await db.commit()
        await update.message.reply_text(
            f"✅ Возраст обновлен: {age}",
            reply_markup=get_personal_data_menu()
        )
        logger.info(f"Сообщение об успешном обновлении возраста отправлено пользователю {user_id}")
        schedule_message_deletion(
            context,
            [user_message_id],
            chat_id,
            delay=5
        )
    except ValueError:
        await update.message.reply_text(
            "⚠️ Пожалуйста, введите корректное число для возраста.",
            reply_markup=get_personal_data_menu()
        )

    context.user_data.pop('current_state', None)
    return ConversationHandler.END