# bot/handlers/profile_input.py
"""
Модуль: profile_input.py
Описание: Модуль содержит обработчики для ввода данных профиля пользователя в рамках ConversationHandler
и определения состояний для диалогов. Обрабатывает ввод имени, возраста, веса, роста, типа тренировок
и команду отмены.

Зависимости:
- sqlite3: Для работы с базой данных SQLite.
- telegram: Для взаимодействия с Telegram API.
- telegram.ext: Для работы с контекстом, обработчиками и ConversationHandler.
- bot.keyboards.personal_data_menu: Для получения меню личных данных.
- bot.keyboards.training_settings_menu: Для получения меню настроек тренировок.
- bot.keyboards.settings_menu: Для получения меню настроек.

Автор: Aksarin A.
Дата создания: 19/08/2025
Версия: 1.0.0
"""

import sqlite3
from telegram import Update
from telegram.ext import (
    ContextTypes,
    ConversationHandler
)

from bot.keyboards.personal_data_menu import get_personal_data_menu
from bot.keyboards.training_settings_menu import get_training_settings_menu
from bot.utils.logger import setup_logging


# Инициализация логгера для записи событий и ошибок.
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
        conn = sqlite3.connect('users.db')
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

async def set_weight(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обработчик ввода веса пользователя.

    Описание:
        Проверяет корректность введенного веса (число с плавающей точкой от 0 до 500),
        сохраняет его в базе данных и возвращает меню личных данных.
        При некорректном вводе отправляет сообщение об ошибке.

    Аргументы:
        update (telegram.Update): Объект обновления, содержащий введенное сообщение.
        context (telegram.ext.ContextTypes.DEFAULT_TYPE): Контекст выполнения команды.

    Возвращаемое значение:
        int: ConversationHandler.END, завершающий диалог.

    Исключения:
        - ValueError: Если введено некорректное значение веса.
        - sqlite3.Error: Если возникают ошибки при работе с базой данных.
        - telegram.error.TelegramError: Если возникают ошибки при отправке сообщения.

    Пример использования:
        Пользователь вводит вес, бот сохраняет его или запрашивает корректный ввод.
    """
    user_id = update.message.from_user.id
    try:
        weight = float(update.message.text.strip())
        if weight < 0 or weight > 500:
            raise ValueError("Некорректный вес")
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute("UPDATE UserSettings SET weight = ? WHERE user_id = ?", (weight, user_id))
        conn.commit()
        conn.close()
        await update.message.reply_text(
            f"✅ Вес обновлен: {weight} кг",
            reply_markup=get_personal_data_menu()
        )
    except ValueError:
        await update.message.reply_text(
            "⚠️ Пожалуйста, введите корректное число для веса (например, 70.5).",
            reply_markup=get_personal_data_menu()
        )
    return ConversationHandler.END

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
        - sqlite3.Error: Если возникают ошибки при работе с базой данных.
        - telegram.error.TelegramError: Если возникают ошибки при отправке сообщения.

    Пример использования:
        Пользователь вводит рост, бот сохраняет его или запрашивает корректный ввод.
    """
    user_id = update.message.from_user.id
    try:
        height = float(update.message.text.strip())
        if height < 0 or height > 300:
            raise ValueError("Некорректный рост")
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute("UPDATE UserSettings SET height = ? WHERE user_id = ?", (height, user_id))
        conn.commit()
        conn.close()
        await update.message.reply_text(
            f"✅ Рост обновлен: {height} см",
            reply_markup=get_personal_data_menu()
        )
    except ValueError:
        await update.message.reply_text(
            "⚠️ Пожалуйста, введите корректное число для роста (например, 175).",
            reply_markup=get_personal_data_menu()
        )
    return ConversationHandler.END

async def set_training_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обработчик ввода типа тренировок.

    Описание:
        Сохраняет введенный пользователем тип тренировок в базе данных и возвращает меню настроек тренировок.

    Аргументы:
        update (telegram.Update): Объект обновления, содержащий введенное сообщение.
        context (telegram.ext.ContextTypes.DEFAULT_TYPE): Контекст выполнения команды.

    Возвращаемое значение:
        int: ConversationHandler.END, завершающий диалог.

    Исключения:
        - sqlite3.Error: Если возникают ошибки при работе с базой данных.
        - telegram.error.TelegramError: Если возникают ошибки при отправке сообщения.

    Пример использования:
        Пользователь вводит тип тренировок, бот сохраняет его и возвращает меню настроек тренировок.
    """
    user_id = update.message.from_user.id
    training_type = update.message.text.strip()
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("UPDATE UserSettings SET training_type = ? WHERE user_id = ?", (training_type, user_id))
    conn.commit()
    conn.close()
    await update.message.reply_text(
        f"✅ Тип тренировок обновлен: {training_type}",
        reply_markup=get_training_settings_menu()
    )
    return ConversationHandler.END
