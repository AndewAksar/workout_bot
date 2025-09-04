# bot/handlers/set_weight.py
"""
Модуль: set_weight.py
Описание: Модуль содержит обработчики для ввода данных профиля пользователя в рамках ConversationHandler
и определения состояний для диалогов. Обрабатывает ввод веса и команду отмены.

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

import os
import sqlite3
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
    chat_id = update.message.chat_id
    user_message_id = update.message.message_id
    weight = float(update.message.text.strip())
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'users.db')

    try:
        logger.info(f"Подключение к базе данных: {DB_PATH}, файл существует: {os.path.exists(DB_PATH)}")
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()

        # Проверка существования таблицы
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='UserSettings'")
        if not c.fetchone():
            logger.error("Таблица UserSettings не существует, вызываем init_db")
            from bot.database.db_init import init_db
            init_db()

        # Проверка существования пользователя
        c.execute("SELECT user_id FROM UserSettings WHERE user_id = ?", (user_id,))
        if not c.fetchone():
            c.execute("INSERT INTO UserSettings (user_id) VALUES (?)", (user_id,))
            conn.commit()

        if weight < 0 or weight > 500:
            logger.warning(f"Пользователь {user_id} отправил некорректные данные: {weight}")
            raise ValueError("⚠️ Некорректный ввод веса (0 - 500 кг).")
        c.execute("UPDATE UserSettings SET weight = ? WHERE user_id = ?", (weight, user_id))
        conn.commit()
        logger.info(f"Вес успешно обновлён для пользователя {user_id}: {weight}")
        await update.message.reply_text(
            f"✅ Вес обновлен: {weight} кг",
            reply_markup=get_personal_data_menu()
        )
        logger.info(f"Сообщение об успешном обновлении веса отправлено пользователю {user_id}")
        await schedule_message_deletion(
            context,
            [user_message_id],
            chat_id,
            delay=5
        )
        conn.close()
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text(
            "⚠️ Пожалуйста, введите корректное число для веса (например, 70.5).",
            reply_markup=get_personal_data_menu()
        )
        return ConversationHandler.END
    except sqlite3.Error as e:
        logger.error(f"Ошибка базы данных для пользователя {user_id}: {e}")
        await update.message.reply_text(
            "❌ Произошла ошибка при сохранении данных. Попробуйте снова.",
            reply_markup=get_personal_data_menu()
        )
        conn.close()

    context.user_data.pop('current_state', None)
    return ConversationHandler.END