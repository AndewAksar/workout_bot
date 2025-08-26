# bot/handlers/set_age.py
"""
Модуль: set_age.py
Описание: Модуль содержит обработчики для ввода данных профиля пользователя в рамках ConversationHandler
и определения состояний для диалогов. Обрабатывает ввод возраста и команду отмены.

Зависимости:
- sqlite3: Для работы с базой данных SQLite.
- telegram: Для взаимодействия с Telegram API.
- telegram.ext: Для работы с контекстом, обработчиками и ConversationHandler.
- bot.keyboards.personal_data_menu: Для получения меню личных данных.
- bot.keyboards.training_settings_menu: Для получения меню настроек тренировок.
- bot.keyboards.settings_menu: Для получения меню настроек.
- bot.utils.logger: Для настройки логирования.

Автор: Aksarin A.
Дата создания: 21/08/2025
"""

import sqlite3
from telegram import Update
from telegram.ext import (
    ContextTypes,
    ConversationHandler
)

from bot.keyboards.personal_data_menu import get_personal_data_menu
from bot.utils.logger import setup_logging
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
        - sqlite3.Error: Если возникают ошибки при работе с базой данных.
        - telegram.error.TelegramError: Если возникают ошибки при отправке сообщения.

    Пример использования:
        Пользователь вводит возраст, бот сохраняет его или запрашивает корректный ввод.
    """
    user_id = update.message.from_user.id
    try:
        age = int(update.message.text.strip())
        if age < 0 or age > 150:
            raise ValueError("Некорректный возраст")
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("UPDATE UserSettings SET age = ? WHERE user_id = ?", (age, user_id))
        conn.commit()
        conn.close()
        await update.message.reply_text(
            f"✅ Возраст обновлен: {age}",
            reply_markup=get_personal_data_menu()
        )
    except ValueError:
        await update.message.reply_text(
            "⚠️ Пожалуйста, введите корректное число для возраста.",
            reply_markup=get_personal_data_menu()
        )
    return ConversationHandler.END