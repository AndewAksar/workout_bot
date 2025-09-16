# bot/handlers/set_height.py
"""
Модуль: set_height.py
Описание: Модуль содержит обработчики для ввода данных профиля пользователя в рамках ConversationHandler
и определения состояний для диалогов. Обрабатывает ввод роста и команду отмены.

Зависимости:
- aiosqlite: Для асинхронной работы с базой данных SQLite.
- telegram: Для взаимодействия с Telegram API.
- telegram.ext: Для работы с контекстом, обработчиками и ConversationHandler.
- bot.keyboards.personal_data_menu: Для получения меню личных данных.
- bot.keyboards.training_settings_menu: Для получения меню настроек тренировок.
- bot.keyboards.settings_menu: Для получения меню настроек.
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

async def set_height(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обработчик ввода роста пользователя.
    Описание:
        Проверяет корректность введенного роста (число с плавающей точкой от 0 до 300),
        сохраняет его в базе данных и возвращает меню личных данных.
        При некорректном вводе отправляет сообщение об ошибке.
    Аргументы:
        update (telegram.Update): Объект обновления, содержащий введенное сообщение.
        context (telegram.ext.ContextTypes.DEFAULT_TYPE): Контекст выполнения команды.
    Возвращаемое значение:
        int: ConversationHandler.END, завершающий диалог.
    Исключения:
        - ValueError: Если введено некорректное значение роста.
        - aiosqlite.Error: Если возникают ошибки при работе с базой данных.
        - telegram.error.TelegramError: Если возникают ошибки при отправке сообщения.
    Пример использования:
        Пользователь вводит рост, бот сохраняет его или запрашивает корректный ввод.
    """
    user_id = update.message.from_user.id
    chat_id = update.message.chat_id
    user_message_id = update.message.message_id

    try:
        height = float(update.message.text.strip())
        if height < 0 or height > 300:
            raise ValueError("Некорректный рост")
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "UPDATE UserSettings SET height = ? WHERE user_id = ?",
                (height, user_id),
            )
            await db.commit()
        await update.message.reply_text(
            f"✅ Рост обновлен: {height} см",
            reply_markup=get_personal_data_menu()
        )
        logger.info(f"Сообщение об успешном обновлении роста отправлено пользователю {user_id}")
        await schedule_message_deletion(
            context,
            [user_message_id],
            chat_id,
            delay=5
        )
    except ValueError:
        await update.message.reply_text(
            "⚠️ Пожалуйста, введите корректное число для роста (например, 175).",
            reply_markup=get_personal_data_menu()
        )

    context.user_data.pop('current_state', None)
    return ConversationHandler.END