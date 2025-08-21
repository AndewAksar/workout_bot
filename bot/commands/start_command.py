# bot/handlers/start_command.py
"""
Модуль: start_command.py
Описание: Модуль содержит обработчик команды /start.

Зависимости:
- sqlite3: Для работы с базой данных SQLite.
- telegram: Для взаимодействия с Telegram API.
- telegram.ext: Для работы с контекстом и обновлениями Telegram.
- bot.config.settings: Для получения конфигурационных данных (WELCOME_MESSAGE).
- bot.keyboards.main_menu: Для генерации главного меню.

Автор: Aksarin A.
Дата создания: 19/08/2025
"""

import sqlite3
from telegram import Update
from telegram.ext import ContextTypes

from bot.config.settings import WELCOME_MESSAGE
from bot.keyboards.main_menu import get_main_menu


# Обработчик команды /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
        Обработчик команды /start.

        Описание:
            Выполняет начальную регистрацию пользователя или обновление его данных в базе данных.
            Извлекает информацию о пользователе (ID, имя, username) и сохраняет её.
            Формирует приветственное сообщение с данными профиля (если они есть) и отправляет его с главным меню.

        Аргументы:
            update (telegram.Update): Объект обновления, содержащий информацию о входящем сообщении.
            context (telegram.ext.ContextTypes.DEFAULT_TYPE): Контекст выполнения команды, предоставляющий доступ к данным бота.

        Возвращаемое значение:
            None

        Исключения:
            - sqlite3.Error: Если возникают ошибки при работе с базой данных.
            - telegram.error.TelegramError: Если возникают ошибки при отправке сообщения.

        Пример использования:
            Пользователь отправляет команду /start, бот отвечает приветственным сообщением и отображает главное меню.
    """
    # Извлечение данных пользователя из объекта Update
    user = update.message.from_user
    user_id = user.id
    username = user.username if user.username else "друг"
    first_name = user.first_name if user.first_name else ""

    # Подключение к базе данных и сохранение/обновление данных пользователя
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute(
        "INSERT OR REPLACE INTO UserSettings (user_id, username, name) VALUES (?, ?, ?)",
        (user_id, username, first_name)
    )
    conn.commit()

    # Получение данных профиля из базы данных
    c.execute(
        "SELECT name, age, weight, height, training_type FROM UserSettings WHERE user_id = ?",
        (user_id,)
    )
    profile = c.fetchone()
    conn.close()

    # Формирование приветственного сообщения
    greeting = (
        f"<b>Привет, {profile[0] or username}! 👋</b>\n"
        f"Твой ID: <code>{user_id}</code>\n\n"
    )
    if profile and any(profile[1:]):  # Проверка наличия дополнительных данных профиля
        greeting += (
            f"\n📋 <b>Твой профиль:</b>\n"
            f"Возраст: {profile[1] if profile[1] else 'Не указан'}\n"
            f"Вес: {profile[2] if profile[2] else 'Не указан'} кг\n"
            f"Рост: {profile[3] if profile[3] else 'Не указан'} см\n"
            f"Тип тренировок: {profile[4] if profile[4] else 'Не указан'}\n"
        )
    greeting += f"{WELCOME_MESSAGE}"

    # Отправка приветственного сообщения с главным меню
    await update.message.reply_text(
        greeting,
        parse_mode="HTML",
        reply_markup=get_main_menu()
    )