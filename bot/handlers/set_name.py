# bot/handlers/set_name.py
"""
Модуль: set_name.py
Описание: Обработчик ввода имени пользователя для ConversationHandler.
Сохраняет имя в базе данных и возвращает меню личных данных.

Зависимости:
- aiosqlite: Для асинхронной работы с базой данных SQLite.
- telegram: Для взаимодействия с Telegram API.
- telegram.ext: Для работы с контекстом и ConversationHandler.
- bot.keyboards.personal_data_menu: Для получения меню личных данных.
- bot.utils.logger: Для логирования событий и ошибок.
- bot.utils.message_deletion: Для планирования удаления сообщений.
- SET_NAME: Константа для идентификации состояния диалога.
"""

import aiosqlite
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from bot.api.gym_stat_client import update_profile
from bot.keyboards.personal_data_menu import get_personal_data_menu
from bot.utils.logger import setup_logging
from bot.utils.message_deletion import schedule_message_deletion
from bot.utils.db_utils import get_user_mode
from bot.utils.api_session import get_valid_access_token
from bot.config.settings import (
    DB_PATH,
    SET_NAME
)

# Инициализация логгера
logger = setup_logging()

async def set_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обработчик ввода имени пользователя.
    Описание:
        Сохраняет введенное пользователем имя в базе данных, возвращает меню личных данных
        и планирует удаление сообщения пользователя и сообщения подтверждения.
    Аргументы:
        update (telegram.Update): Объект обновления, содержащий введенное сообщение.
        context (telegram.ext.ContextTypes.DEFAULT_TYPE): Контекст выполнения команды.
    Возвращаемое значение:
        int: ConversationHandler.END, завершающий диалог.
    Исключения:
        - aiosqlite.Error: Если возникают ошибки при работе с базой данных.
        - telegram.error.TelegramError: Если возникают ошибки при отправке сообщения.
    Пример использования:
        Пользователь вводит имя, бот сохраняет его, отправляет подтверждение и планирует
        удаление сообщения пользователя.
    """
    logger.info("Функция set_name вызвана")
    user_id = update.message.from_user.id
    chat_id = update.message.chat_id
    name = update.message.text.strip()
    user_message_id = update.message.message_id

    logger.info(f"Начало обработки ввода имени для пользователя {user_id}: {name}")

    if not name or len(name) > 50:  # Пример ограничения длины имени
        logger.warning(f"Пользователь {user_id} отправил некорректное имя: {name}")
        error_message = await update.message.reply_text(
            "⚠️ Имя не может быть пустым или длиннее 50 символов. Пожалуйста, введите корректное имя:",
            reply_markup=None
        )
        schedule_message_deletion(
            context,
            [user_message_id, error_message.message_id],
            chat_id,
            delay=10
        )
        return SET_NAME

    mode = await get_user_mode(user_id)
    if mode == 'api':
        token = await get_valid_access_token(user_id)
        if not token:
            error_message = await update.message.reply_text(
                "🔐 Требуется вход. Используйте /login.",
                reply_markup=get_personal_data_menu(),
            )
            schedule_message_deletion(
                context,
                [user_message_id, error_message.message_id],
                chat_id,
                delay=5,
            )
            context.user_data['conversation_active'] = False
            return ConversationHandler.END
        try:
            resp = await update_profile(token, {"name": name})
        except Exception as e:
            logger.error(
                f"Ошибка при запросе обновления имени через API для пользователя {user_id}: {str(e)}"
            )
            error_message = await update.message.reply_text(
                "⚠️ Не удалось сохранить имя. Попробуйте позже.",
                reply_markup=get_personal_data_menu(),
            )
            schedule_message_deletion(
                context,
                [user_message_id, error_message.message_id],
                chat_id,
                delay=5,
            )
            context.user_data['conversation_active'] = False
            return ConversationHandler.END
        if resp.status_code != 200:
            logger.warning(
                "Не удалось обновить имя через API для пользователя %s: %s %s",
                user_id,
                resp.status_code,
                resp.text,
            )
            error_message = await update.message.reply_text(
                "⚠️ Не удалось сохранить имя. Попробуйте снова.",
                reply_markup=get_personal_data_menu(),
            )
            schedule_message_deletion(
                context,
                [user_message_id, error_message.message_id],
                chat_id,
                delay=5,
            )
            context.user_data['conversation_active'] = False
            return ConversationHandler.END
    else:
        try:
            async with aiosqlite.connect(DB_PATH) as db:
                async with db.execute(
                        "SELECT user_id FROM UserSettings WHERE user_id = ?",
                        (user_id,),
                ) as cursor:
                    exists = await cursor.fetchone()
                if not exists:
                    await db.execute(
                        "INSERT INTO UserSettings (user_id) VALUES (?)",
                        (user_id,),
                    )
                    await db.commit()
                    logger.info(f"Создана новая запись для пользователя {user_id}")
                await db.execute(
                    "UPDATE UserSettings SET name = ? WHERE user_id = ?",
                    (name, user_id),
                )
                await db.commit()
                logger.info(f"Имя успешно обновлено для пользователя {user_id}: {name}")
        except aiosqlite.Error as e:
            logger.error(
                f"Ошибка базы данных при обновлении имени для пользователя {user_id}: {str(e)}"
            )
            error_message = await update.message.reply_text(
                "⚠️ Произошла ошибка при сохранении имени. Попробуйте снова.",
                reply_markup=get_personal_data_menu(),
            )
            schedule_message_deletion(
                context,
                [user_message_id, error_message.message_id],
                chat_id,
                delay=5,
            )
            context.user_data['conversation_active'] = False
            return ConversationHandler.END
        except Exception as e:
            logger.error(
                f"Ошибка при обработке ввода имени для пользователя {user_id}: {str(e)}"
            )
            context.user_data['conversation_active'] = False
            return ConversationHandler.END

    try:
        await update.message.reply_text(
            (
                f"✅ Имя обновлено: <b>{name}</b>.\n"
                "Оно отобразится в профиле и приветствиях."
                " Проверьте раздел «👤 Показать профиль» или продолжайте"
                " заполнять данные через кнопки ниже."
            ),
            parse_mode="HTML",
            reply_markup=get_personal_data_menu(),
        )
        logger.info(
            f"Сообщение об успешном обновлении имени отправлено пользователю {user_id}"
        )
        schedule_message_deletion(
            context,
            [user_message_id],
            chat_id,
            delay=5,
        )
    except Exception as e:
        logger.error(
            f"Ошибка при отправке сообщения подтверждения пользователю {user_id}: {str(e)}"
        )
        context.user_data['conversation_active'] = False
        return ConversationHandler.END

    logger.debug(
        f"Завершение обработки ввода имени для пользователя {user_id}"
    )
    context.user_data['conversation_active'] = False
    context.user_data.pop('current_state', None)
    return ConversationHandler.END

