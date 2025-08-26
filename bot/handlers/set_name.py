# bot/handlers/set_name.py
"""
Модуль: set_name.py
Описание: Обработчик ввода имени пользователя для ConversationHandler.
Сохраняет имя в базе данных и возвращает меню личных данных.

Зависимости:
- sqlite3: Для работы с базой данных SQLite.
- telegram: Для взаимодействия с Telegram API.
- telegram.ext: Для работы с контекстом и ConversationHandler.
- bot.keyboards.personal_data_menu: Для получения меню личных данных.
- bot.utils.logger: Для логирования событий и ошибок.
- SET_NAME: Константа для идентификации состояния диалога.

Автор: Aksarin A.
Дата создания: 21/08/2025
"""

import sqlite3
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from bot.keyboards.personal_data_menu import get_personal_data_menu
from bot.utils.logger import setup_logging
from bot.handlers.callbacks import SET_NAME
from bot.config.settings import DB_PATH

# Инициализация логгера
logger = setup_logging()

async def set_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обработчик ввода имени пользователя.
    Описание:
        Сохраняет введенное пользователем имя в базе данных и возвращает меню личных данных.
        Логирует начало выполнения, успешное сохранение и возможные ошибки.
    Аргументы:
        update (telegram.Update): Объект обновления, содержащий введенное сообщение.
        context (telegram.ext.ContextTypes.DEFAULT_TYPE): Контекст выполнения команды.
    Возвращаемое значение:
        int: ConversationHandler.END, завершающий диалог.
    Исключения:
        - sqlite3.Error: Если возникают ошибки при работе с базой данных.
        - telegram.error.TelegramError: Если возникают ошибки при отправке сообщения.

    Пример использования:
        Пользователь вводит имя, бот сохраняет его и возвращает меню личных данных.
    """
    logger.info("Функция set_name вызвана")

    user_id = update.message.from_user.id
    name = update.message.text.strip()

    logger.info(f"Начало обработки ввода имени для пользователя {user_id}: {name}")

    if not name or len(name) > 50:  # Пример ограничения длины имени
        logger.warning(f"Пользователь {user_id} отправил некорректное имя: {name}")
        await update.message.reply_text(
            "⚠️ Имя не может быть пустым или длиннее 50 символов. Пожалуйста, введите корректное имя:",
            reply_markup=None
        )
        return SET_NAME

    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT user_id FROM UserSettings WHERE user_id = ?", (user_id,))
        if not c.fetchone():
            c.execute("INSERT INTO UserSettings (user_id) VALUES (?)", (user_id,))
            conn.commit()
            logger.info(f"Создана новая запись для пользователя {user_id}")
        c.execute("UPDATE UserSettings SET name = ? WHERE user_id = ?", (name, user_id))
        conn.commit()
        logger.info(f"Имя успешно обновлено для пользователя {user_id}: {name}")
    except sqlite3.Error as e:
        logger.error(f"Ошибка базы данных при обновлении имени для пользователя {user_id}: {str(e)}")
        await update.message.reply_text(
            "⚠️ Произошла ошибка при сохранении имени. Попробуйте снова.",
            reply_markup=get_personal_data_menu()
        )
    except Exception as e:
        logger.error(f"Ошибка при отправке сообщения пользователю {user_id}: {str(e)}")
        conn.close()
        return ConversationHandler.END
    finally:
        conn.close()

    try:
        await update.message.reply_text(
            f"✅ Имя обновлено: {name}",
            reply_markup=get_personal_data_menu()
        )
        logger.info(f"Сообщение об успешном обновлении имени отправлено пользователю {user_id}")
    except Exception as e:
        logger.error(f"Ошибка при отправке сообщения пользователю {user_id}: {str(e)}")
        return ConversationHandler.END

    logger.debug(f"Завершение обработки ввода имени для пользователя {user_id}")
    return ConversationHandler.END