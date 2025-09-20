# bot/handlers/body_params.py
"""Обработчик отображения замеров тела пользователя."""

from __future__ import annotations

import html
from typing import Any, Callable

import aiosqlite
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes, ConversationHandler

from bot.config.settings import (
    DB_PATH,
    SET_BODY_PARAM,
)
from bot.handlers.set_age import set_age
from bot.handlers.set_gender import set_gender
from bot.handlers.set_height import set_height
from bot.handlers.set_name import set_name
from bot.handlers.set_weight import set_weight
from bot.utils.db_utils import get_user_mode
from bot.utils.formatters import format_gender
from bot.utils.logger import setup_logging

logger = setup_logging()

BodyParamHandler = Callable[[Update, ContextTypes.DEFAULT_TYPE], Any]


def _get_body_params_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("Имя", callback_data="body_param_set_name")],
        [
            InlineKeyboardButton("Пол", callback_data="body_param_set_gender"),
            InlineKeyboardButton("Возраст", callback_data="body_param_set_age"),
        ],
        [
            InlineKeyboardButton("Вес", callback_data="body_param_set_weight"),
            InlineKeyboardButton("Рост", callback_data="body_param_set_height"),
        ],
        [
            InlineKeyboardButton(
                "🗑️ Очистить значения",
                callback_data="body_param_delete_all",
            )
        ],
        [InlineKeyboardButton("🔙 Назад", callback_data="settings")],
    ]
    return InlineKeyboardMarkup(keyboard)


async def _ensure_user_row(db: aiosqlite.Connection, user_id: int) -> None:
    async with db.execute(
        "SELECT 1 FROM UserSettings WHERE user_id = ?",
        (user_id,),
    ) as cursor:
        if await cursor.fetchone():
            return
    await db.execute(
        "INSERT INTO UserSettings (user_id) VALUES (?)",
        (user_id,),
    )


async def _fetch_body_params(user_id: int) -> dict[str, Any]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            """
            SELECT name, gender, age, weight, height
            FROM UserSettings
            WHERE user_id = ?
            """,
            (user_id,),
        ) as cursor:
            row = await cursor.fetchone()
    if not row:
        return {
            "name": None,
            "gender": None,
            "age": None,
            "weight": None,
            "height": None,
        }
    return {
        "name": row[0],
        "gender": row[1],
        "age": row[2],
        "weight": row[3],
        "height": row[4],
    }


def _format_value(param: str, value: Any) -> str:
    if value is None or value == "":
        return "<i>Не указано</i>"
    if param == "gender":
        return html.escape(format_gender(value))
    if isinstance(value, (int, float)):
        formatted = format(value, "g")
        return html.escape(formatted)
    return html.escape(str(value))


PARAM_CONFIG: dict[str, dict[str, Any]] = {
    "name": {
        "title": "Имя",
        "prompt": (
            "✍️ <b>Введите имя</b>\n"
            "Например: <code>Иван</code>. /cancel — отменить ввод."
        ),
        "handler": set_name,
        "state_key": "SET_NAME",
    },
    "gender": {
        "title": "Пол",
        "prompt": (
            "✍️ <b>Введите пол</b> в формате <code>мужской</code> или <code>женский</code>."
            " /cancel — отмена."
        ),
        "handler": set_gender,
        "state_key": "SET_GENDER",
    },
    "age": {
        "title": "Возраст",
        "prompt": (
            "✍️ <b>Введите возраст</b> — целое число от 0 до 150."
            " Пример: <code>29</code>. /cancel — отменить."
        ),
        "handler": set_age,
        "state_key": "SET_AGE",
    },
    "weight": {
        "title": "Вес",
        "prompt": lambda mode: (
            "✍️ <b>Введите вес</b> в килограммах."
            " Можно использовать точку или запятую: пример <code>70.5</code>."
            " /cancel — отменить."
            if mode != "api"
            else (
                "✍️ <b>Добавьте взвешивание</b>. Введите вес в кг — запись"
                " сразу появится в истории Gym-Stat. /cancel — отменить."
            )
        ),
        "handler": set_weight,
        "state_key": "SET_WEIGHT",
    },
    "height": {
        "title": "Рост",
        "prompt": (
            "✍️ <b>Введите рост</b> в сантиметрах. Пример: <code>175</code>."
            " /cancel — отменить ввод."
        ),
        "handler": set_height,
        "state_key": "SET_HEIGHT",
    },
}

PARAM_ORDER = ["name", "gender", "age", "weight", "height"]


async def _render_body_params_text(user_id: int) -> str:
    values = await _fetch_body_params(user_id)
    lines = [
        "📊 <b>Параметры тела</b>",
        "Здесь собраны основные показатели. Выберите пункт ниже, чтобы обновить значение.",
        "",
    ]
    for key in PARAM_ORDER:
        config = PARAM_CONFIG[key]
        value = _format_value(key, values.get(key))
        if value.startswith("<i>"):
            lines.append(f"• {config['title']}: {value}")
        else:
            lines.append(f"• {config['title']}: <code>{value}</code>")
    lines.append(
        "\nНажмите нужную кнопку, чтобы изменить показатель, или очистите их все."
    )
    return "\n".join(lines)


async def show_body_params(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if not query:
        logger.warning("show_body_params вызван без callback_query")
        return ConversationHandler.END
    await query.answer()
    user_id = query.from_user.id
    logger.info("Пользователь %s открыл меню параметров тела", user_id)

    context.user_data.pop("pending_body_param", None)
    context.user_data.pop("current_state", None)
    context.user_data["conversation_active"] = False

    try:
        text = await _render_body_params_text(user_id)
    except aiosqlite.Error as exc:  # noqa: BLE001
        logger.error(
            "Ошибка чтения параметров тела пользователя %s: %s",
            user_id,
            exc,
        )
        await query.message.edit_text(
            "❌ Не удалось получить сохранённые параметры. Попробуйте позже.",
            parse_mode="HTML",
            reply_markup=_get_body_params_keyboard(),
        )
        return ConversationHandler.END

    await query.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=_get_body_params_keyboard(),
    )
    return ConversationHandler.END


async def prompt_body_param(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if not query:
        logger.warning("prompt_body_param вызван без callback_query")
        return ConversationHandler.END
    await query.answer()

    user_id = query.from_user.id
    raw_data = query.data or ""
    param_key = raw_data.replace("body_param_set_", "", 1)
    config = PARAM_CONFIG.get(param_key)
    if not config:
        logger.warning("Неизвестный параметр %s для пользователя %s", raw_data, user_id)
        if query.message:
            await query.message.reply_text(
                "⚠️ Неизвестный параметр. Вернитесь в меню и попробуйте снова.",
            )
        return ConversationHandler.END

    try:
        mode = await get_user_mode(user_id)
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "Не удалось определить режим пользователя %s перед вводом параметра: %s",
            user_id,
            exc,
        )
        mode = "local"
    prompt_text = config["prompt"]
    if callable(prompt_text):
        prompt_message = prompt_text(mode)
    else:
        prompt_message = prompt_text

    context.user_data["pending_body_param"] = param_key
    context.user_data["conversation_active"] = True
    context.user_data["current_state"] = "SET_BODY_PARAM"

    await query.message.edit_text(
        prompt_message,
        parse_mode="HTML",
        reply_markup=None,
    )
    logger.info(
        "Пользователь %s запрашивает обновление параметра %s",
        user_id,
        param_key,
    )
    return SET_BODY_PARAM


async def handle_body_param_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    param_key = context.user_data.get("pending_body_param")
    if not param_key:
        logger.warning("handle_body_param_input вызван без pending_body_param")
        if update.message:
            await update.message.reply_text(
                "⚠️ Используйте меню параметров, чтобы изменить значение.",
            )
        context.user_data["conversation_active"] = False
        context.user_data.pop("current_state", None)
        return ConversationHandler.END

    config = PARAM_CONFIG.get(param_key)
    handler: BodyParamHandler | None = None
    state_key = None
    if config:
        handler = config.get("handler")
        state_key = config.get("state_key")
    if not handler:
        logger.error("Не найден обработчик для параметра %s", param_key)
        context.user_data.pop("pending_body_param", None)
        context.user_data["conversation_active"] = False
        context.user_data.pop("current_state", None)
        if update.message:
            await update.message.reply_text(
                "⚠️ Не удалось обновить параметр. Попробуйте снова через меню.",
            )
        return ConversationHandler.END

    if state_key:
        context.user_data["current_state"] = state_key

    try:
        result = await handler(update, context)
    finally:
        context.user_data.pop("pending_body_param", None)
        if context.user_data.get("current_state") == "SET_BODY_PARAM":
            context.user_data.pop("current_state", None)
    return result


async def delete_body_params(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if not query:
        logger.warning("delete_body_params вызван без callback_query")
        return ConversationHandler.END
    await query.answer()

    user_id = query.from_user.id
    logger.info("Пользователь %s очищает параметры тела", user_id)
    context.user_data.pop("pending_body_param", None)
    context.user_data["conversation_active"] = False
    context.user_data.pop("current_state", None)

    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await _ensure_user_row(db, user_id)
            await db.execute(
                """
                UPDATE UserSettings
                SET name = NULL,
                    age = NULL,
                    weight = NULL,
                    height = NULL,
                    gender = NULL
                WHERE user_id = ?
                """,
                (user_id,),
            )
            await db.commit()
    except aiosqlite.Error as exc:  # noqa: BLE001
        logger.error(
            "Ошибка очистки параметров тела пользователя %s: %s",
            user_id,
            exc,
        )
        await query.message.edit_text(
            "❌ Не удалось очистить данные. Попробуйте позже.",
            parse_mode="HTML",
            reply_markup=_get_body_params_keyboard(),
        )
        return ConversationHandler.END

    try:
        text = await _render_body_params_text(user_id)
    except aiosqlite.Error as exc:  # noqa: BLE001
        logger.error(
            "Ошибка повторного чтения параметров после очистки для пользователя %s: %s",
            user_id,
            exc,
        )
        await query.message.edit_text(
            "✅ Все параметры очищены.",
            parse_mode="HTML",
            reply_markup=_get_body_params_keyboard(),
        )
        return ConversationHandler.END

    await query.message.edit_text(
        "✅ Все параметры очищены.\n\n" + text,
        parse_mode="HTML",
        reply_markup=_get_body_params_keyboard(),
    )
    return ConversationHandler.END