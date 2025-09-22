# bot/handlers/body_params.py
"""Обработчики отображения и обновления параметров тела пользователя через Gym-Stat."""

from __future__ import annotations

import html
import re
from datetime import datetime, timezone
from typing import Any, Iterable, Tuple

import httpx
from telegram import Update
from telegram.error import BadRequest, TelegramError
from telegram.ext import ContextTypes, ConversationHandler

from bot.api.gym_stat_client import (
    create_body_params as api_create_body_params,
    delete_body_params as api_delete_body_params,
    get_body_params as api_get_body_params,
    update_body_params as api_update_body_params,
)
from bot.config.settings import SET_BODY_PARAM
from bot.keyboards.body_params_menu import get_body_params_menu
from bot.utils.api_session import get_valid_access_token
from bot.utils.db_utils import get_user_mode
from bot.utils.logger import setup_logging
from bot.utils.message_deletion import schedule_message_deletion

logger = setup_logging()

DATE_INPUT_PATTERN = re.compile(r"^(0[1-9]|[12][0-9]|3[01])\.(0[1-9]|1[0-2])\.\d{4}$")

FIELD_TITLES = {
    "date": "Дата замеров",
    "neck": "Шея",
    "chest": "Грудь",
    "waist": "Талия",
    "hips": "Бёдра",
    "thigh": "Бедро",
    "calf": "Икра",
    "forearm": "Предплечье",
    "wrist": "Запястье",
}

MEASUREMENT_KEYS = [
    "neck",
    "chest",
    "waist",
    "hips",
    "thigh",
    "calf",
    "forearm",
    "wrist",
]

CARD_ORDER = ["date", *MEASUREMENT_KEYS]


def _empty_values() -> dict[str, Any]:
    """Возвращает словарь со всеми ключами окружностей, заполненный значениями None."""

    return {"date": None, **{key: None for key in MEASUREMENT_KEYS}}


def _draft_ready_for_save(draft: dict[str, Any] | None) -> bool:
    """Проверяет, достаточно ли данных в черновике для отправки на сервер."""

    if not isinstance(draft, dict):
        return False

    date = draft.get("date")
    if not date:
        return False

    has_measurements = any(
        draft.get(key) not in (None, "") for key in MEASUREMENT_KEYS
    )
    return has_measurements


def _normalize_entries(payload: Any) -> list[dict[str, Any]]:
    """Приводит ответ API к списку словарей."""

    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("data", "results", "items", "records"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        if any(key in payload for key in ("uuid", "date", "createdAt", "created_at")):
            return [payload]
    return []


def _parse_datetime(value: Any) -> datetime | None:
    """Преобразует строку или datetime в объект datetime для сортировки."""

    if not value:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        normalized = value.strip().replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(normalized)
        except ValueError:
            try:
                dt = datetime.strptime(normalized, "%Y-%m-%d")
            except ValueError:
                return None
        if dt.tzinfo:
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt
    return None


def _entry_sort_key(entry: dict[str, Any]) -> datetime:
    """Возвращает ключ сортировки для записи обмеров."""

    for field in ("date", "createdAt", "created_at", "updatedAt", "updated_at"):
        dt = _parse_datetime(entry.get(field))
        if dt:
            return dt
    return datetime.min


def _normalize_mm_value(value: Any) -> float | None:
    """Преобразует значение окружности в число с плавающей точкой."""

    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text:
        return None
    try:
        return float(text.replace(",", "."))
    except ValueError:
        return None


def _normalize_date_value(value: Any) -> str | None:
    """Преобразует дату к формату YYYY-MM-DD."""

    if not value:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, str):
        text = value.strip()
        if DATE_INPUT_PATTERN.match(text):
            dt = datetime.strptime(text, "%d.%m.%Y")
            return dt.date().isoformat()
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
            return text
        normalized = text.replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(normalized)
        except ValueError:
            return None
        if dt.tzinfo:
            dt = dt.astimezone(timezone.utc)
        return dt.date().isoformat()
    return None


def _format_date_for_display(value: Any) -> str | None:
    """Форматирует дату для отображения пользователю."""

    iso_value = _normalize_date_value(value)
    if not iso_value:
        return None
    try:
        dt = datetime.strptime(iso_value, "%Y-%m-%d")
    except ValueError:
        return None
    return dt.strftime("%d.%m.%Y")


def _format_mm(value: Any) -> str:
    """Возвращает форматированное значение окружности в мм."""

    if value is None:
        return "<i>Не указано</i>"
    if isinstance(value, (int, float)):
        formatted = f"{float(value):.1f}".rstrip("0").rstrip(".")
        return f"<code>{formatted}</code> мм"
    text = str(value).strip()
    if not text:
        return "<i>Не указано</i>"
    try:
        number = float(text.replace(",", "."))
    except ValueError:
        return html.escape(text)
    formatted = f"{number:.1f}".rstrip("0").rstrip(".")
    return f"<code>{formatted}</code> мм"


def _build_card_text(values: dict[str, Any] | None, status: str | None = None) -> str:
    """Формирует текстовую карточку с обмерами."""

    lines: list[str] = ["📏 <b>Обмеры тела</b>"]
    if status:
        lines.append(status)
    lines.append(
        "Эти окружности в миллиметрах мы используем для расчёта процента жира и персональных рекомендаций."
    )
    lines.append("")

    if not values:
        lines.append("📭 Пока нет сохранённых замеров.")
        lines.append(
            "Начните с кнопки «Дата» или добавьте любую окружность — мы создадим запись в Gym-Stat автоматически."
        )
        return "\n".join(lines)

    display_date = _format_date_for_display(values.get("date"))
    if display_date:
        lines.append(f"🗓️ {FIELD_TITLES['date']}: <code>{display_date}</code>")
    else:
        lines.append(f"🗓️ {FIELD_TITLES['date']}: <i>Не указана</i>")
    lines.append("")

    for key in MEASUREMENT_KEYS:
        title = FIELD_TITLES[key]
        lines.append(f"• {title}: {_format_mm(values.get(key))}")

    lines.append("")
    lines.append("Обновите показатели через кнопки ниже — мы синхронизируем данные с Gym-Stat.")
    return "\n".join(lines)


def _store_entry(context: ContextTypes.DEFAULT_TYPE, entry: dict[str, Any] | None) -> dict[str, Any]:
    """Сохраняет текущие значения обмеров в контексте пользователя."""

    values = _empty_values()

    if entry:
        uuid = entry.get("uuid") or entry.get("id")
        if uuid:
            context.user_data["body_params_uuid"] = uuid
        else:
            context.user_data.pop("body_params_uuid", None)
        iso_date = _normalize_date_value(
            entry.get("date")
            or entry.get("measurementDate")
            or entry.get("measurement_date")
            or entry.get("createdAt")
            or entry.get("created_at")
        )
        if iso_date:
            values["date"] = iso_date
        for key in MEASUREMENT_KEYS:
            values[key] = _normalize_mm_value(entry.get(key))
    else:
        context.user_data.pop("body_params_uuid", None)

    context.user_data["body_params_values"] = values
    context.user_data["body_params_draft"] = {**values}
    context.user_data["body_params_dirty"] = False
    return values


def _extract_error_message(response: httpx.Response) -> str | None:
    """Извлекает сообщение об ошибке из ответа API."""

    try:
        payload = response.json()
    except ValueError:
        text = response.text.strip()
        return text or None

    if isinstance(payload, dict):
        for key in ("detail", "message", "error"):
            value = payload.get(key)
            if isinstance(value, str):
                return value
        errors = payload.get("errors")
        if isinstance(errors, Iterable):
            for item in errors:
                if isinstance(item, str):
                    return item
    return None


async def _fetch_latest_entry(token: str) -> Tuple[dict[str, Any] | None, str | None]:
    """Получает последнюю запись обмеров через API."""

    try:
        response = await api_get_body_params(token)
    except httpx.HTTPError as exc:  # noqa: BLE001
        logger.error("Ошибка HTTP при запросе обмеров тела: %s", exc)
        return None, "Не удалось связаться с Gym-Stat. Попробуйте позже."
    except Exception as exc:  # noqa: BLE001
        logger.error("Неожиданная ошибка при запросе обмеров тела: %s", exc)
        return None, "Не удалось загрузить параметры. Попробуйте позже."

    if response.status_code >= 400:
        logger.warning(
            "Gym-Stat вернул %s при получении обмеров: %s",
            response.status_code,
            response.text,
        )
        error_text = _extract_error_message(response)
        return None, error_text or "Не удалось получить параметры. Попробуйте позже."

    try:
        payload = response.json()
    except ValueError:
        logger.error("Некорректный JSON при запросе обмеров: %s", response.text)
        return None, "Сервер Gym-Stat вернул некорректный ответ."

    entries = _normalize_entries(payload)
    if not entries:
        return None, None

    latest = max(entries, key=_entry_sort_key)
    return latest, None


async def _load_and_store(context: ContextTypes.DEFAULT_TYPE, token: str) -> tuple[dict[str, Any] | None, str | None]:
    """Загружает последнюю запись и сохраняет её в контексте."""

    entry, error = await _fetch_latest_entry(token)
    if entry:
        values = _store_entry(context, entry)
    else:
        context.user_data.pop("body_params_uuid", None)
        values = _empty_values()
        context.user_data["body_params_values"] = values
        context.user_data["body_params_draft"] = {**values}
        context.user_data["body_params_dirty"] = False
    return values, error


async def _refresh_card(
    context: ContextTypes.DEFAULT_TYPE,
    *,
    chat_id: int,
    message_id: int | None,
    token: str | None,
    status: str | None = None,
    skip_fetch: bool = False,
) -> None:
    """Перерисовывает карточку с обмерами."""

    values: dict[str, Any] | None = None
    status_message = status
    dirty = bool(context.user_data.get("body_params_dirty"))
    has_saved_data = bool(context.user_data.get("body_params_uuid"))

    if not skip_fetch and token and not dirty:
        values, error = await _load_and_store(context, token)
        if error and not status_message:
            status_message = f"❌ {html.escape(error)}"
        has_saved_data = bool(context.user_data.get("body_params_uuid"))
    else:
        values = context.user_data.get("body_params_draft") or context.user_data.get("body_params_values")

    if values is None:
        values = _empty_values()

    if dirty:
        unsaved_hint = "💾 Черновик не сохранён."
        if status_message:
            if unsaved_hint not in status_message:
                status_message = f"{status_message}\n{unsaved_hint}"
        else:
            status_message = unsaved_hint

    can_save = dirty and _draft_ready_for_save(context.user_data.get("body_params_draft"))

    text = _build_card_text(values, status=status_message)
    keyboard = get_body_params_menu(has_data=has_saved_data, can_save=can_save)

    if message_id is not None:
        try:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=text,
                parse_mode="HTML",
                reply_markup=keyboard,
            )
            context.user_data["body_params_message"] = (chat_id, message_id)
            return
        except (BadRequest, TelegramError) as exc:
            logger.warning("Не удалось обновить сообщение с параметрами тела: %s", exc)

    sent = await context.bot.send_message(
        chat_id=chat_id,
        text=text,
        parse_mode="HTML",
        reply_markup=keyboard,
    )
    context.user_data["body_params_message"] = (sent.chat_id, sent.message_id)


async def _render_placeholder(
    query, context: ContextTypes.DEFAULT_TYPE, text: str
) -> None:
    """Отображает заглушку и сбрасывает сохранённые данные."""

    context.user_data.pop("body_params_uuid", None)
    empty_values = _empty_values()
    context.user_data["body_params_values"] = empty_values
    context.user_data["body_params_draft"] = {**empty_values}
    context.user_data["body_params_dirty"] = False

    message = getattr(query, "message", None)
    if not message:
        return

    await message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=get_body_params_menu(has_data=False),
    )
    context.user_data["body_params_message"] = (message.chat_id, message.message_id)


async def show_body_params(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Показывает последнюю запись обмеров пользователя."""

    query = update.callback_query
    if not query:
        logger.warning("show_body_params вызван без callback_query")
        return ConversationHandler.END

    await query.answer()
    user_id = query.from_user.id

    context.user_data.pop("pending_body_param", None)
    context.user_data.pop("current_state", None)
    context.user_data["conversation_active"] = False

    mode = await get_user_mode(user_id)
    if mode != "api":
        await _render_placeholder(
            query,
            context,
            (
                "🌐 <b>Доступно в режиме Gym-Stat</b>\n"
                "Подключите аккаунт Gym-Stat, чтобы видеть и обновлять измерения тела."
            ),
        )
        return ConversationHandler.END

    token = await get_valid_access_token(user_id)
    if not token:
        await _render_placeholder(
            query,
            context,
            (
                "🔐 <b>Требуется авторизация</b>\n"
                "Войдите через /login, чтобы загрузить замеры из Gym-Stat."
            ),
        )
        return ConversationHandler.END

    values, error = await _load_and_store(context, token)
    status = f"❌ {html.escape(error)}" if error else None

    message = query.message
    chat_id = message.chat_id if message else query.from_user.id
    message_id = message.message_id if message else None

    await _refresh_card(
        context,
        chat_id=chat_id,
        message_id=message_id,
        token=None,
        status=status,
        skip_fetch=True,
    )
    return ConversationHandler.END


async def prompt_body_param(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Запрашивает у пользователя значение конкретного параметра."""

    query = update.callback_query
    if not query:
        logger.warning("prompt_body_param вызван без callback_query")
        return ConversationHandler.END

    await query.answer()
    raw_data = query.data or ""
    if not raw_data.startswith("body_param_"):
        logger.warning("Получен неизвестный callback: %s", raw_data)
        return ConversationHandler.END

    param_key = raw_data.replace("body_param_", "", 1)
    if param_key not in FIELD_TITLES:
        logger.warning("Неизвестный параметр %s", param_key)
        return ConversationHandler.END

    user_id = query.from_user.id
    mode = await get_user_mode(user_id)
    if mode != "api":
        await _render_placeholder(
            query,
            context,
            (
                "🌐 <b>Доступно в режиме Gym-Stat</b>\n"
                "Переключитесь на интеграцию, чтобы редактировать параметры."
            ),
        )
        return ConversationHandler.END

    token = await get_valid_access_token(user_id)
    if not token:
        await _render_placeholder(
            query,
            context,
            (
                "🔐 <b>Нужна авторизация</b>\n"
                "Используйте /login, чтобы продолжить работу с замерами."
            ),
        )
        return ConversationHandler.END

    values = context.user_data.get("body_params_draft") or context.user_data.get("body_params_values", {})

    prompt_lines: list[str] = []
    if param_key == "date":
        prompt_lines.append("✍️ <b>Введите дату замеров</b>")
        current_date = _format_date_for_display(values.get("date"))
        if current_date:
            prompt_lines.append(f"Текущее значение: <code>{current_date}</code>")
        prompt_lines.append("Формат: <code>ДД.ММ.ГГГГ</code>.")
        prompt_lines.append("/cancel — отменить ввод.")
    else:
        title = FIELD_TITLES[param_key]
        prompt_lines.append(f"✍️ <b>Введите окружность для «{title}»</b>")
        current_value = values.get(param_key)
        if current_value not in (None, ""):
            prompt_lines.append(f"Сейчас: {_format_mm(current_value)}")
        prompt_lines.append("Укажите значение в миллиметрах (например, <code>420</code>).")
        prompt_lines.append("/cancel — отменить ввод.")

    context.user_data["pending_body_param"] = param_key
    context.user_data["conversation_active"] = True
    context.user_data["current_state"] = "SET_BODY_PARAM"

    message = query.message
    if message:
        await message.edit_text("\n".join(prompt_lines), parse_mode="HTML")
        context.user_data["body_params_message"] = (message.chat_id, message.message_id)

    return SET_BODY_PARAM


async def handle_body_param_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает текстовый ввод значения параметра."""

    message = update.message
    if message is None:
        return ConversationHandler.END

    user_id = message.from_user.id
    chat_id = message.chat_id
    user_message_id = message.message_id
    param_key = context.user_data.get("pending_body_param")

    if not param_key:
        warning = await message.reply_text(
            "⚠️ Используйте меню параметров, чтобы обновить значение."
        )
        schedule_message_deletion(
            context,
            [user_message_id, warning.message_id],
            chat_id,
            delay=10,
        )
        context.user_data["conversation_active"] = False
        context.user_data.pop("current_state", None)
        return ConversationHandler.END

    mode = await get_user_mode(user_id)
    if mode != "api":
        warning = await message.reply_text(
            "🌐 Изменение обмеров доступно только после подключения Gym-Stat."
        )
        schedule_message_deletion(
            context,
            [user_message_id, warning.message_id],
            chat_id,
            delay=10,
        )
        context.user_data["conversation_active"] = False
        context.user_data.pop("pending_body_param", None)
        context.user_data.pop("current_state", None)
        return ConversationHandler.END

    message_info = context.user_data.get("body_params_message")
    card_chat_id, card_message_id = (message_info or (chat_id, None))

    raw_text = (message.text or "").strip()

    async def _abort_with_error(text: str, status: str) -> int:
        reply = await message.reply_text(text)
        schedule_message_deletion(
            context,
            [user_message_id, reply.message_id],
            chat_id,
            delay=10,
        )
        await _refresh_card(
            context,
            chat_id=card_chat_id,
            message_id=card_message_id,
            token=None,
            status=status,
            skip_fetch=True,
        )
        context.user_data["conversation_active"] = False
        context.user_data.pop("pending_body_param", None)
        context.user_data.pop("current_state", None)
        return ConversationHandler.END

    if param_key == "date":
        if not DATE_INPUT_PATTERN.match(raw_text):
            return await _abort_with_error(
                "⚠️ Введите дату в формате ДД.ММ.ГГГГ.",
                "⚠️ Неверный формат даты. Попробуйте ещё раз.",
            )
        dt = datetime.strptime(raw_text, "%d.%m.%Y")
        payload_value: Any = dt.date().isoformat()
    else:
        normalized = raw_text.replace(",", ".")
        try:
            value = float(normalized)
        except ValueError:
            return await _abort_with_error(
                "⚠️ Пожалуйста, введите число в миллиметрах (например, 420).",
                "⚠️ Некорректное значение. Укажите окружность в мм.",
            )
        if value <= 0 or value > 2000:
            return await _abort_with_error(
                "⚠️ Допустимый диапазон окружностей — от 1 до 2000 мм.",
                "⚠️ Значение вне допустимого диапазона.",
            )
        payload_value = int(round(value)) if abs(value - round(value)) < 1e-4 else round(value, 1)

    draft = context.user_data.get("body_params_draft")
    if not isinstance(draft, dict):
        base = context.user_data.get("body_params_values")
        draft = {**base} if isinstance(base, dict) else _empty_values()

    updated_draft = {**draft, param_key: payload_value}
    context.user_data["body_params_draft"] = updated_draft

    saved_values = context.user_data.get("body_params_values")
    is_dirty = True
    if isinstance(saved_values, dict):
        is_dirty = any(
            saved_values.get(field) != updated_draft.get(field)
            for field in CARD_ORDER
        )
    context.user_data["body_params_dirty"] = is_dirty

    if not is_dirty:
        status_message = "ℹ️ Изменений нет — значения совпадают с сохранёнными."
    else:
        status_message = (
            "✏️ Дата замеров обновлена в черновике."
            if param_key == "date"
            else f"✏️ «{FIELD_TITLES[param_key]}» обновлено в черновике."
        )

    await _refresh_card(
        context,
        chat_id=card_chat_id,
        message_id=card_message_id,
        token=None,
        status=status_message,
        skip_fetch=True,
    )

    schedule_message_deletion(context, [user_message_id], chat_id, delay=5)
    context.user_data["conversation_active"] = False
    context.user_data.pop("pending_body_param", None)
    context.user_data.pop("current_state", None)
    return ConversationHandler.END


async def cancel_body_param_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отменяет ввод параметра тела, сохраняя черновик."""

    message = update.message
    if message is None:
        return ConversationHandler.END

    chat_id = message.chat_id
    message_id = message.message_id

    message_info = context.user_data.get("body_params_message")
    card_chat_id, card_message_id = message_info or (chat_id, None)

    await _refresh_card(
        context,
        chat_id=card_chat_id,
        message_id=card_message_id,
        token=None,
        status="ℹ️ Ввод отменён.",
        skip_fetch=True,
    )

    schedule_message_deletion(context, [message_id], chat_id, delay=5)
    context.user_data["conversation_active"] = False
    context.user_data.pop("pending_body_param", None)
    context.user_data.pop("current_state", None)
    return ConversationHandler.END


async def save_body_params(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Сохраняет черновик замеров тела в Gym-Stat."""

    query = update.callback_query
    if not query:
        logger.warning("save_body_params вызван без callback_query")
        return ConversationHandler.END

    await query.answer()
    user_id = query.from_user.id

    context.user_data.pop("pending_body_param", None)
    context.user_data.pop("current_state", None)
    context.user_data["conversation_active"] = False

    draft = context.user_data.get("body_params_draft")
    dirty = bool(context.user_data.get("body_params_dirty"))

    message = query.message
    message_info = context.user_data.get("body_params_message")
    card_chat_id, card_message_id = (
        message_info
        or ((message.chat_id if message else user_id), None)
    )

    if not dirty:
        await _refresh_card(
            context,
            chat_id=card_chat_id,
            message_id=card_message_id,
            token=None,
            status="ℹ️ Нет изменений для сохранения.",
            skip_fetch=True,
        )
        return ConversationHandler.END

    if not _draft_ready_for_save(draft):
        await _refresh_card(
            context,
            chat_id=card_chat_id,
            message_id=card_message_id,
            token=None,
            status="⚠️ Укажите дату и хотя бы одну окружность, чтобы сохранить запись.",
            skip_fetch=True,
        )
        return ConversationHandler.END

    mode = await get_user_mode(user_id)
    if mode != "api":
        await _render_placeholder(
            query,
            context,
            (
                "🌐 <b>Только для режима Gym-Stat</b>\n"
                "Переключитесь на интеграцию, чтобы сохранить измерения."
            ),
        )
        return ConversationHandler.END

    token = await get_valid_access_token(user_id)
    if not token:
        await _render_placeholder(
            query,
            context,
            (
                "🔐 <b>Нет активной сессии</b>\n"
                "Авторизуйтесь через /login, чтобы продолжить."
            ),
        )
        return ConversationHandler.END

    payload = {
        field: draft.get(field)
        for field in CARD_ORDER
        if isinstance(draft, dict) and draft.get(field) not in (None, "")
    }

    uuid = context.user_data.get("body_params_uuid")
    is_update = bool(uuid)

    try:
        if uuid:
            response = await api_update_body_params(token, uuid, payload)
        else:
            response = await api_create_body_params(token, payload)
    except httpx.HTTPError as exc:  # noqa: BLE001
        logger.error("Ошибка HTTP при сохранении обмеров: %s", exc)
        await _refresh_card(
            context,
            chat_id=card_chat_id,
            message_id=card_message_id,
            token=None,
            status="❌ Не удалось отправить данные. Попробуйте позже.",
            skip_fetch=True,
        )
        return ConversationHandler.END
    except Exception as exc:  # noqa: BLE001
        logger.error("Неожиданная ошибка при сохранении обмеров: %s", exc)
        await _refresh_card(
            context,
            chat_id=card_chat_id,
            message_id=card_message_id,
            token=None,
            status="❌ Произошла ошибка при сохранении параметров.",
            skip_fetch=True,
        )
        return ConversationHandler.END

    if response.status_code >= 400:
        error_text = _extract_error_message(response) or "Не удалось сохранить запись."
        await _refresh_card(
            context,
            chat_id=card_chat_id,
            message_id=card_message_id,
            token=None,
            status=f"❌ {html.escape(error_text)}",
            skip_fetch=True,
        )
        return ConversationHandler.END

    new_entry: dict[str, Any] | None = None
    try:
        payload_data = response.json()
    except ValueError:
        payload_data = None

    if payload_data is not None:
        entries = _normalize_entries(payload_data)
        if entries:
            new_entry = max(entries, key=_entry_sort_key)

    if new_entry:
        _store_entry(context, new_entry)
    else:
        cleaned_values = _empty_values()
        if isinstance(draft, dict):
            for field in CARD_ORDER:
                value = draft.get(field)
                if value not in (None, ""):
                    cleaned_values[field] = value
        context.user_data["body_params_values"] = cleaned_values
        context.user_data["body_params_draft"] = {**cleaned_values}
        context.user_data["body_params_dirty"] = False
        if uuid:
            context.user_data["body_params_uuid"] = uuid

    saved_uuid = context.user_data.get("body_params_uuid")
    if not saved_uuid and isinstance(new_entry, dict):
        extracted_uuid = new_entry.get("uuid") or new_entry.get("id")
        if extracted_uuid:
            context.user_data["body_params_uuid"] = extracted_uuid

    status_message = (
        "✅ Запись обмеров обновлена."
        if is_update
        else "✅ Запись обмеров создана."
    )

    await _refresh_card(
        context,
        chat_id=card_chat_id,
        message_id=card_message_id,
        token=None,
        status=status_message,
        skip_fetch=True,
    )

    return ConversationHandler.END


async def delete_body_params(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Удаляет текущую запись обмеров пользователя."""

    query = update.callback_query
    if not query:
        logger.warning("delete_body_params вызван без callback_query")
        return ConversationHandler.END

    await query.answer()
    user_id = query.from_user.id

    context.user_data.pop("pending_body_param", None)
    context.user_data.pop("current_state", None)
    context.user_data["conversation_active"] = False

    mode = await get_user_mode(user_id)
    if mode != "api":
        await _render_placeholder(
            query,
            context,
            (
                "🌐 <b>Только для режима Gym-Stat</b>\n"
                "Переключитесь на интеграцию, чтобы управлять измерениями."
            ),
        )
        return ConversationHandler.END

    token = await get_valid_access_token(user_id)
    if not token:
        await _render_placeholder(
            query,
            context,
            (
                "🔐 <b>Нет активной сессии</b>\n"
                "Авторизуйтесь через /login, чтобы продолжить."
            ),
        )
        return ConversationHandler.END

    uuid = context.user_data.get("body_params_uuid")
    message = query.message
    message_info = context.user_data.get("body_params_message")
    card_chat_id, card_message_id = (message_info or ((message.chat_id if message else user_id), None))

    if not uuid:
        await _refresh_card(
            context,
            chat_id=card_chat_id,
            message_id=card_message_id,
            token=token,
            status="⚠️ Нет сохранённых данных для удаления.",
            skip_fetch=True,
        )
        return ConversationHandler.END

    try:
        response = await api_delete_body_params(token, uuid)
    except httpx.HTTPError as exc:  # noqa: BLE001
        logger.error("Ошибка HTTP при удалении обмеров: %s", exc)
        await _refresh_card(
            context,
            chat_id=card_chat_id,
            message_id=card_message_id,
            token=token,
            status="❌ Не удалось удалить запись. Попробуйте позже.",
            skip_fetch=True,
        )
        return ConversationHandler.END
    except Exception as exc:  # noqa: BLE001
        logger.error("Неожиданная ошибка при удалении обмеров: %s", exc)
        await _refresh_card(
            context,
            chat_id=card_chat_id,
            message_id=card_message_id,
            token=token,
            status="❌ Не удалось удалить запись. Попробуйте позже.",
            skip_fetch=True,
        )
        return ConversationHandler.END

    if response.status_code >= 400:
        error_text = _extract_error_message(response) or "Не удалось удалить запись."
        await _refresh_card(
            context,
            chat_id=card_chat_id,
            message_id=card_message_id,
            token=token,
            status=f"❌ {html.escape(error_text)}",
            skip_fetch=True,
        )
        return ConversationHandler.END

    # После успешного удаления сбрасываем сохранённые значения и черновик
    context.user_data.pop("body_params_uuid", None)
    empty_values = _empty_values()
    context.user_data["body_params_values"] = empty_values
    context.user_data["body_params_draft"] = {**empty_values}
    context.user_data["body_params_dirty"] = False

    await _refresh_card(
        context,
        chat_id=card_chat_id,
        message_id=card_message_id,
        token=token,
        status="✅ Последняя запись удалена.",
    )

    return ConversationHandler.END

