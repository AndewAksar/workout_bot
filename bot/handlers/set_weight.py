# bot/handlers/set_weight.py
"""
Модуль: set_weight.py
Описание: Модуль содержит обработчики для ввода данных профиля пользователя в рамках ConversationHandler
и определения состояний для диалогов. Обрабатывает ввод веса и команду отмены.

Зависимости:
- aiosqlite: Для асинхронной работы с базой данных SQLite.
- telegram: Для взаимодействия с Telegram API.
- telegram.ext: Для работы с контекстом, обработчиками и ConversationHandler.
- bot.api.gym_stat_client: Для отправки данных о взвешиваниях на сервер Gym-Stat.
- bot.keyboards.personal_data_menu: Для получения меню личных данных.
- bot.utils.api_session: Для получения валидного access-токена Gym-Stat.
- bot.utils.db_utils: Для определения активного режима пользователя.
- bot.utils.message_deletion: Для планирования удаления сообщений.
"""

import asyncio
import os
import aiosqlite
import httpx
from datetime import datetime, timezone
from telegram import Message, Update
from telegram.ext import ContextTypes, ConversationHandler

from bot.api.gym_stat_client import create_weight_data
from bot.keyboards.personal_data_menu import get_personal_data_menu
from bot.utils.api_session import get_valid_access_token
from bot.utils.db_utils import get_user_mode
from bot.utils.logger import setup_logging
from bot.utils.message_deletion import schedule_message_deletion
from bot.config.settings import DB_PATH


logger = setup_logging()


async def _ensure_user_row(db: aiosqlite.Connection, user_id: int) -> None:
    """Создаёт запись в таблице UserSettings при её отсутствии."""
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


async def _init_table_if_required(db: aiosqlite.Connection) -> None:
    """Проверяет наличие таблицы UserSettings и инициализирует БД при необходимости."""
    async with db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='UserSettings'",
    ) as cursor:
        if await cursor.fetchone():
            return
    logger.error("Таблица UserSettings не существует, вызываем init_db")
    from bot.database.db_init import init_db

    await asyncio.to_thread(init_db)


async def _send_error(
    message: Message,
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    user_message_id: int,
    text: str,
    delay: int = 10,
) -> None:
    """Отправляет сообщение об ошибке и планирует его удаление."""
    error_message = await message.reply_text(
        text,
        reply_markup=get_personal_data_menu(),
    )
    schedule_message_deletion(
        context,
        [user_message_id, error_message.message_id],
        chat_id,
        delay=delay,
    )


async def set_weight(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает ввод веса в локальном и API-режимах."""
    message = update.message
    if message is None:
        return ConversationHandler.END

    user_id = message.from_user.id
    chat_id = message.chat_id
    user_message_id = message.message_id
    raw_text = (message.text or "").strip()

    try:
        weight = float(raw_text.replace(",", "."))
    except ValueError:
        logger.warning("Пользователь %s отправил некорректный вес: %s", user_id, raw_text)
        await _send_error(
            message,
            context,
            chat_id,
            user_message_id,
            "⚠️ Пожалуйста, введите корректное число для веса (например, 70.5).",
        )
        context.user_data["conversation_active"] = False
        context.user_data.pop("current_state", None)
        return ConversationHandler.END
    if weight < 0 or weight > 500:
        logger.warning("Пользователь %s отправил некорректные данные: %s", user_id, weight)
        await _send_error(
            message,
            context,
            chat_id,
            user_message_id,
            "⚠️ Некорректный ввод веса (допустимо 0 - 500 кг).",
        )
        context.user_data["conversation_active"] = False
        context.user_data.pop("current_state", None)
        return ConversationHandler.END
    mode = await get_user_mode(user_id)
    if mode == "api":
        token = await get_valid_access_token(user_id)
        if not token:
            logger.warning("Не удалось получить access_token для пользователя %s", user_id)
            await _send_error(
                message,
                context,
                chat_id,
                user_message_id,
                "🔐 Требуется авторизация. Используйте /login.",
            )
            context.user_data["conversation_active"] = False
            context.user_data.pop("current_state", None)
            return ConversationHandler.END

        payload = {
            "weight": weight,
            "date": datetime.now(timezone.utc)
            .isoformat(timespec="milliseconds")
            .replace("+00:00", "Z"),
        }

        try:
            response = await create_weight_data(token, payload)
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "Ошибка при отправке данных взвешивания через API для пользователя %s: %s",
                user_id,
                exc,
            )
            await _send_error(
                message,
                context,
                chat_id,
                user_message_id,
                "⚠️ Не удалось сохранить вес. Попробуйте позже.",
            )
            context.user_data["conversation_active"] = False
            context.user_data.pop("current_state", None)
            return ConversationHandler.END

        if response.status_code >= 400:
            logger.warning(
                "Не удалось сохранить вес через API для пользователя %s: %s %s",
                user_id,
                response.status_code,
                response.text,
            )
            error_text = "⚠️ Не удалось сохранить вес. Попробуйте снова."
            try:
                payload_json = response.json()
                if isinstance(payload_json, dict):
                    detail = payload_json.get("detail") or payload_json.get("message")
                    if isinstance(detail, str):
                        error_text = f"⚠️ {detail}"
            except ValueError:
                pass
            await _send_error(
                message,
                context,
                chat_id,
                user_message_id,
                error_text,
            )
            context.user_data["conversation_active"] = False
            context.user_data.pop("current_state", None)
            return ConversationHandler.END

        try:
            saved_payload = response.json()
        except ValueError:
            saved_payload = {}

        saved_weight = saved_payload.get("weight", weight)
        saved_date = saved_payload.get("date") or payload["date"]
        display_date = saved_date
        if saved_date:
            try:
                display_date = (
                    datetime.fromisoformat(saved_date.replace("Z", "+00:00"))
                    .strftime("%d.%m.%Y %H:%M")
                )
            except ValueError:
                display_date = saved_date

        confirmation = (
            f"✅ Вес обновлен: {saved_weight} кг"
            if not display_date
            else f"✅ Вес обновлен: {saved_weight} кг (от {display_date})"
        )

        await message.reply_text(
            confirmation,
            reply_markup=get_personal_data_menu(),
        )
        schedule_message_deletion(
            context,
            [user_message_id],
            chat_id,
            delay=5,
        )

        context.user_data["conversation_active"] = False
        context.user_data.pop("current_state", None)
        return ConversationHandler.END

    try:
        logger.info(
            "Подключение к базе данных: %s, файл существует: %s",
            DB_PATH,
            os.path.exists(DB_PATH),
        )
        async with aiosqlite.connect(DB_PATH) as db:
            await _init_table_if_required(db)
            await _ensure_user_row(db, user_id)
            await db.execute(
                "UPDATE UserSettings SET weight = ? WHERE user_id = ?",
                (weight, user_id),
            )
            await db.commit()
    except aiosqlite.Error as exc:
        logger.error(
            "Ошибка базы данных для пользователя %s: %s",
            user_id,
            exc,
        )
        await _send_error(
            message,
            context,
            chat_id,
            user_message_id,
            "❌ Произошла ошибка при сохранении данных. Попробуйте снова.",
        )
        context.user_data["conversation_active"] = False
        context.user_data.pop("current_state", None)
        return ConversationHandler.END

    logger.info("Вес успешно обновлён для пользователя %s: %s", user_id, weight)
    await message.reply_text(
        f"✅ Вес обновлен: {weight} кг",
        reply_markup=get_personal_data_menu(),
    )
    schedule_message_deletion(
        context,
        [user_message_id],
        chat_id,
        delay=5,
    )
    context.user_data["conversation_active"] = False
    context.user_data.pop("current_state", None)
    return ConversationHandler.END