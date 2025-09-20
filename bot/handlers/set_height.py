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

from bot.api.gym_stat_client import update_profile
from bot.config.settings import DB_PATH
from bot.keyboards.personal_data_menu import get_personal_data_menu
from bot.utils.api_session import get_valid_access_token
from bot.utils.db_utils import get_user_mode
from bot.utils.logger import setup_logging
from bot.utils.message_deletion import schedule_message_deletion

logger = setup_logging()

async def set_height(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обработчик ввода роста пользователя.
    Описание:
        Проверяет корректность введенного роста (число с плавающей точкой от 0 до 300),
        сохраняет его в базе данных или через API и возвращает меню личных данных.
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
    message = update.message
    if message is None:
        context.user_data["conversation_active"] = False
        context.user_data.pop("current_state", None)
        return ConversationHandler.END

    user_id = message.from_user.id
    chat_id = message.chat_id
    user_message_id = message.message_id
    raw_height = (message.text or "").strip()

    logger.info("Начало обработки ввода роста для пользователя %s: %s", user_id, raw_height)

    try:
        height = float(raw_height.replace(",", "."))
        if height < 0 or height > 300:
            raise ValueError
    except ValueError:
        logger.warning("Пользователь %s отправил некорректное значение роста: %s", user_id, raw_height)
        error_message = await message.reply_text(
            "⚠️ Пожалуйста, введите корректное число для роста (например, 175).",
            reply_markup=get_personal_data_menu(),
        )

        schedule_message_deletion(
            context,
            [user_message_id, error_message.message_id],
            chat_id,
            delay = 5,
        )
        context.user_data["conversation_active"] = False
        context.user_data.pop("current_state", None)
        return ConversationHandler.END

    mode = await get_user_mode(user_id)
    if mode == "api":
        token = await get_valid_access_token(user_id)
        if not token:
            logger.warning("Не удалось получить access_token для пользователя %s", user_id)
            error_message = await message.reply_text(
                "🔐 Требуется вход. Используйте /login.",
                reply_markup=get_personal_data_menu(),
            )
            schedule_message_deletion(
                context,
                [user_message_id, error_message.message_id],
                chat_id,
                delay=5,
            )
            context.user_data["conversation_active"] = False
            context.user_data.pop("current_state", None)
            return ConversationHandler.END

        try:
            response = await update_profile(token, {"heightCm": height})
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "Ошибка при запросе обновления роста через API для пользователя %s: %s",
                user_id,
                exc,
            )
            error_message = await message.reply_text(
                "⚠️ Не удалось сохранить рост. Попробуйте позже.",
                reply_markup=get_personal_data_menu(),
            )
            schedule_message_deletion(
                context,
                [user_message_id, error_message.message_id],
                chat_id,
                delay=5,
            )
            context.user_data["conversation_active"] = False
            context.user_data.pop("current_state", None)
            return ConversationHandler.END

        if response.status_code != 200:
            logger.warning(
                "Не удалось обновить рост через API для пользователя %s: %s %s",
                user_id,
                response.status_code,
                response.text,
            )
            error_text = "⚠️ Не удалось сохранить рост. Попробуйте снова."
            try:
                response_json = response.json()
                if isinstance(response_json, dict):
                    detail = response_json.get("detail") or response_json.get("message")
                    if isinstance(detail, str) and detail:
                        error_text = f"⚠️ {detail}"
            except ValueError:
                pass
            error_message = await message.reply_text(
                error_text,
                reply_markup=get_personal_data_menu(),
            )
            schedule_message_deletion(
                context,
                [user_message_id, error_message.message_id],
                chat_id,
                delay=5,
            )
            context.user_data["conversation_active"] = False
            context.user_data.pop("current_state", None)
            return ConversationHandler.END
    else:
        try:
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute(
                    "UPDATE UserSettings SET height = ? WHERE user_id = ?",
                    (height, user_id),
                )
                await db.commit()
        except aiosqlite.Error as exc:
            logger.error(
                "Ошибка базы данных при обновлении роста пользователя %s: %s",
                user_id,
                exc,
            )
            error_message = await message.reply_text(
                "⚠️ Произошла ошибка при сохранении роста. Попробуйте снова.",
                reply_markup=get_personal_data_menu(),
            )
            schedule_message_deletion(
                context,
                [user_message_id, error_message.message_id],
                chat_id,
                delay=5,
            )
            context.user_data["conversation_active"] = False
            context.user_data.pop("current_state", None)
            return ConversationHandler.END

    confirmation_message = await message.reply_text(
        f"✅ Рост обновлен: {height:g} см",
        reply_markup=get_personal_data_menu(),
    )
    schedule_message_deletion(
        context,
        [user_message_id, confirmation_message.message_id],
        chat_id,
        delay=5,
    )
    logger.info(
        "Сообщение об успешном обновлении роста отправлено пользователю %s",
        user_id,
    )

    context.user_data["conversation_active"] = False
    context.user_data.pop("current_state", None)
    context.user_data.pop("height", None)
    return ConversationHandler.END