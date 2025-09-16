# bot/handlers/set_gender.py
"""
Модуль: set_gender.py
Описание: Модуль содержит обработчики для ввода пола пользователя в рамках ConversationHandler
и определения состояний для диалогов. Обрабатывает ввод пола пользователя и команду отмены.

Зависимости:
- aiosqlite: Для асинхронной работы с базой данных SQLite.
- telegram: Для взаимодействия с Telegram API.
- telegram.ext: Для работы с контекстом, обработчиками и ConversationHandler.
- bot.keyboards.personal_data_menu: Для получения меню личных данных.
- bot.keyboards.training_settings_menu: Для получения меню настроек тренировок.
- bot.keyboards.settings_menu: Для получения меню настроек.
- bot.utils.logger: Для настройки логирования.
"""

import asyncio
import os
import aiosqlite
from telegram import Update
from telegram.ext import (
    ContextTypes,
    ConversationHandler
)

from bot.config.settings import (
    DB_PATH,
    SET_GENDER
)
from bot.keyboards.personal_data_menu import get_personal_data_menu
from bot.utils.logger import setup_logging
from bot.utils.message_deletion import schedule_message_deletion

logger = setup_logging()

async def set_gender(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обработчик ввода пола пользователя.
    Описание:
        Сохраняет введенный пол пользователем и возвращает в меню настроек.
    Аргументы:
        update (telegram.Update): Объект обновления, содержащий введенное сообщение.
        context (telegram.ext.ContextTypes.DEFAULT_TYPE): Контекст выполнения команды.
    Возвращаемое значение:
        int: ConversationHandler.END, завершающий диалог.
    Исключения:
        - sqlite3.Error: Если возникают ошибки при работе с базой данных.
        - aiosqlite.Error: Если возникают ошибки при работе с базой данных.
    Пример использования:
        Пользователь вводит свой пол, бот сохраняет его и возвращает меню настроек тренировок.
    """
    logger.info("Функция set_gender вызвана")

    user_id = update.message.from_user.id
    chat_id = update.message.chat_id
    user_message_id = update.message.message_id
    gender = update.message.text.strip()

    logger.info(f"Начало обработки ввода пола пользователя {user_id}: {gender}")

    try:
        logger.info(f"Подключение к базе данных: {DB_PATH}, файл существует: {os.path.exists(DB_PATH)}")
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='UserSettings'",
            ) as cursor:
                if not await cursor.fetchone():
                    logger.error("Таблица UserSettings не существует, вызываем init_db")
                    from bot.database.db_init import init_db
                    await asyncio.to_thread(init_db)
            async with db.execute(
                "SELECT user_id FROM UserSettings WHERE user_id = ?",
                (user_id,),
            ) as cursor:
                user_exists = await cursor.fetchone()
            if not user_exists:
                await db.execute(
                    "INSERT INTO UserSettings (user_id) VALUES (?)",
                    (user_id,),
                )
                await db.commit()

            normalized_gender = gender.lower()
            if normalized_gender in ["мужской", "женский"]:
                await db.execute(
                    "UPDATE UserSettings SET gender = ? WHERE user_id = ?",
                    (normalized_gender, user_id),
                )
                await db.commit()
                logger.info(f"Пол успешно обновлён для пользователя {user_id}: {gender}")
                await update.message.reply_text(
                    "✅ Пол успешно обновлён!",
                    reply_markup=get_personal_data_menu()
                )
                logger.info(f"Сообщение об успешном обновлении пола отправлено пользователю {user_id}")
                schedule_message_deletion(
                    context,
                    [user_message_id],
                    chat_id,
                    delay=5
                )
                return ConversationHandler.END
            logger.warning(f"Пользователь {user_id} отправил некорректные данные: {gender}")
            await update.message.reply_text(
                "⚠️ Пожалуйста, введите корректные данные (мужской/женский):",
                reply_markup=None
            )

            return SET_GENDER
    except aiosqlite.Error as e:
        logger.error(f"Ошибка базы данных для пользователя {user_id}: {e}")
        await update.message.reply_text(
            "❌ Произошла ошибка при сохранении данных. Попробуйте снова.",
            reply_markup=get_personal_data_menu()
        )
        return ConversationHandler.END
    except Exception as e:
        logger.error(f"Неизвестная ошибка для пользователя {user_id}: {e}")
        await update.message.reply_text(
            "❌ Произошла неизвестная ошибка. Попробуйте снова.",
            reply_markup=get_personal_data_menu()
        )

    context.user_data.pop('current_state', None)
    return ConversationHandler.END


