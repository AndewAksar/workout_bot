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
from telegram import Message, Update
from telegram.ext import (
    ContextTypes,
    ConversationHandler
)

from bot.api.gym_stat_client import get_profile, update_profile
from bot.config.settings import (
    DB_PATH,
    SET_GENDER
)
from bot.keyboards.personal_data_menu import get_personal_data_menu
from bot.utils.api_session import get_valid_access_token
from bot.utils.db_utils import get_user_mode
from bot.utils.logger import setup_logging
from bot.utils.message_deletion import schedule_message_deletion


logger = setup_logging()


GENDER_MAP = {
    "мужской": "male",
    "женский": "female",
    "male": "male",
    "female": "female",
}


async def _reply_and_finish(
    message: Message,
    context: ContextTypes.DEFAULT_TYPE,
    text: str,
    *,
    reply_markup=None,
    delete_user_message: bool = False,
    delete_bot_message: bool = False,
    delay: int = 5,
) -> int:
    """Отправляет ответ пользователю и завершает диалог."""
    sent_message = await message.reply_text(text, reply_markup=reply_markup)
    messages_to_delete: list[int] = []
    if delete_user_message:
        messages_to_delete.append(message.message_id)
    if delete_bot_message and sent_message:
        messages_to_delete.append(sent_message.message_id)
    if messages_to_delete:
        schedule_message_deletion(
            context,
            messages_to_delete,
            message.chat_id,
            delay=delay,
        )
    context.user_data["conversation_active"] = False
    context.user_data.pop("current_state", None)
    return ConversationHandler.END


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
    message = update.message
    if message is None:
        context.user_data["conversation_active"] = False
        context.user_data.pop("current_state", None)
        return ConversationHandler.END

    user_id = message.from_user.id
    gender = (message.text or "").strip()

    logger.info(f"Начало обработки ввода пола пользователя {user_id}: {gender}")

    normalized_gender = gender.lower()
    mapped_gender = GENDER_MAP.get(normalized_gender)
    if not mapped_gender:
        logger.warning(f"Пользователь {user_id} отправил некорректные данные: {gender}")
        await message.reply_text(
            "⚠️ Пожалуйста, введите корректные данные (мужской/женский):",
            reply_markup=None
        )
        return SET_GENDER

    mode = await get_user_mode(user_id)
    if mode == "api":
        token = await get_valid_access_token(user_id)
        if not token:
            logger.warning("Не удалось получить access_token для пользователя %s", user_id)
            return await _reply_and_finish(
                message,
                context,
                "🔐 Требуется вход. Используйте /login.",
                reply_markup=get_personal_data_menu(),
                delete_user_message=True,
                delete_bot_message=True,
            )

        try:
            profile_response = await get_profile(token)
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "Ошибка при получении профиля пользователя %s: %s",
                user_id,
                exc,
            )
            return await _reply_and_finish(
                message,
                context,
                "⚠️ Не удалось обновить данные. Попробуйте позже.",
                reply_markup=get_personal_data_menu(),
                delete_user_message=True,
                delete_bot_message=True,
            )

        if profile_response.status_code != 200:
            logger.warning(
                "Не удалось получить профиль пользователя %s: %s %s",
                user_id,
                profile_response.status_code,
                profile_response.text,
            )
            return await _reply_and_finish(
                message,
                context,
                "⚠️ Не удалось обновить данные. Попробуйте позже.",
                reply_markup=get_personal_data_menu(),
                delete_user_message=True,
                delete_bot_message=True,
            )

        try:
            profile_data = profile_response.json()
        except ValueError:
            logger.error(
                "Некорректный ответ профиля пользователя %s: %s",
                user_id,
                profile_response.text,
            )
            profile_data = {}
        if not isinstance(profile_data, dict):
            logger.error(
                "Ответ профиля пользователя %s имеет неожиданный формат: %s",
                user_id,
                profile_data,
            )
            profile_data = {}

        current_name_raw = (profile_data or {}).get("name")
        current_name = str(current_name_raw).strip() if current_name_raw is not None else ""
        if not current_name:
            return await _reply_and_finish(
                message,
                context,
                "ℹ️ Сначала задайте имя через кнопку «Имя» или команду.",
                reply_markup=get_personal_data_menu(),
                delete_user_message=True,
                delete_bot_message=True,
            )

        payload = {
            "name": current_name,
            "gender": mapped_gender,
        }

        try:
            response = await update_profile(token, payload)
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "Ошибка при запросе обновления пола через API для пользователя %s: %s",
                user_id,
                exc,
            )
            return await _reply_and_finish(
                message,
                context,
                "⚠️ Не удалось обновить данные. Попробуйте позже.",
                reply_markup=get_personal_data_menu(),
                delete_user_message=True,
                delete_bot_message=True,
            )

        if response.status_code != 200:
            logger.warning(
                "Не удалось обновить пол через API для пользователя %s: %s %s",
                user_id,
                response.status_code,
                response.text,
            )
            error_text = "⚠️ Не удалось обновить данные. Попробуйте снова."
            try:
                response_json = response.json()
                if isinstance(response_json, dict):
                    detail = response_json.get("detail") or response_json.get("message")
                    if isinstance(detail, str) and detail:
                        error_text = f"⚠️ {detail}"
            except ValueError:
                pass
            return await _reply_and_finish(
                message,
                context,
                error_text,
                reply_markup=get_personal_data_menu(),
                delete_user_message=True,
                delete_bot_message=True,
            )

        logger.info(
            "Пол успешно обновлён через API для пользователя %s: %s",
            user_id,
            mapped_gender,
        )

        return await _reply_and_finish(
            message,
            context,
            "✅ Пол успешно обновлён!",
            reply_markup=get_personal_data_menu(),
            delete_user_message=True,
            delay=5,
        )

    try:
        logger.info(
            f"Подключение к базе данных: {DB_PATH}, файл существует: {os.path.exists(DB_PATH)}"
        )
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
            await db.execute(
                "UPDATE UserSettings SET gender = ? WHERE user_id = ?",
                (normalized_gender, user_id),
            )
            await db.commit()
            logger.info(f"Пол успешно обновлён для пользователя {user_id}: {gender}")
    except aiosqlite.Error as e:
        logger.error(f"Ошибка базы данных для пользователя {user_id}: {e}")
        return await _reply_and_finish(
            message,
            context,
            "❌ Произошла ошибка при сохранении данных. Попробуйте снова.",
            reply_markup=get_personal_data_menu(),
            delete_user_message=True,
            delete_bot_message=True,
        )
    except Exception as e:  # noqa: BLE001
        logger.error(f"Неизвестная ошибка для пользователя {user_id}: {e}")
        return await _reply_and_finish(
            message,
            context,
            "❌ Произошла неизвестная ошибка. Попробуйте снова.",
            reply_markup=get_personal_data_menu(),
            delete_user_message=True,
            delete_bot_message=True,
        )

    logger.info(
        f"Сообщение об успешном обновлении пола отправлено пользователю {user_id}"
    )
    return await _reply_and_finish(
        message,
        context,
        "✅ Пол успешно обновлён!",
        reply_markup=get_personal_data_menu(),
        delete_user_message=True,
        delay=5,
    )