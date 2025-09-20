# bot/handlers/weight_data.py
"""
Модуль: weight_data.py
Описание: Обработчик отображения истории взвешиваний пользователя с пагинацией.

Зависимости:
- telegram, telegram.ext: Для взаимодействия с Telegram API.
- bot.api.gym_stat_client: Для получения данных взвешиваний через Gym-Stat API.
- bot.utils.api_session: Для получения access-токена пользователя.
- bot.utils.db_utils: Для определения текущего режима работы пользователя.
- bot.keyboards.settings_menu: Для клавиатуры настроек (кнопка возврата).
- bot.utils.logger: Для логирования событий и ошибок.
"""

from __future__ import annotations

import html
import math
import re
from datetime import datetime, timezone
from typing import Any, Iterable, List

import httpx
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import BadRequest, TelegramError
from telegram.ext import ContextTypes, ConversationHandler

from bot.api.gym_stat_client import get_weight_data as api_get_weight_data
from bot.keyboards.settings_menu import get_settings_menu
from bot.utils.api_session import get_valid_access_token
from bot.utils.db_utils import get_user_mode
from bot.utils.logger import setup_logging


logger = setup_logging()

PAGE_SIZE = 5

# Названия месяцев в именительном и родительном падежах для форматирования.
MONTH_NAMES_RU = {
    1: ("Январь", "января"),
    2: ("Февраль", "февраля"),
    3: ("Март", "марта"),
    4: ("Апрель", "апреля"),
    5: ("Май", "мая"),
    6: ("Июнь", "июня"),
    7: ("Июль", "июля"),
    8: ("Август", "августа"),
    9: ("Сентябрь", "сентября"),
    10: ("Октябрь", "октября"),
    11: ("Ноябрь", "ноября"),
    12: ("Декабрь", "декабря"),
}


def _extract_page(callback_data: str | None) -> int:
    """Извлекает номер страницы из callback_data."""

    if not callback_data:
        return 1
    match = re.search(r"weight_data_page_(\d+)", callback_data)
    if match:
        try:
            page = int(match.group(1))
            return max(page, 1)
        except ValueError:
            logger.warning("Не удалось преобразовать номер страницы из callback_data: %s", callback_data)
    return 1


def _normalize_items(payload: Any) -> List[dict]:
    """Приводит ответ API к списку записей."""

    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("data", "results", "items"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    return []


def _parse_iso_datetime(value: Any) -> datetime | None:
    """Преобразует строку ISO-формата в datetime."""

    if not value:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        normalized = value.replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(normalized)
            if dt.tzinfo:
                dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
            return dt
        except ValueError:
            pass
        try:
            return datetime.strptime(normalized, "%Y-%m-%d")
        except ValueError:
            return None
    return None


def _format_weight(value: Any) -> str:
    """Форматирует значение веса для отображения."""

    if value is None:
        return "Не указан"
    if isinstance(value, (int, float)):
        formatted = f"{value:.2f}".rstrip("0").rstrip(".")
        return formatted
    return str(value)


def _format_month_header(dt: datetime | None) -> str:
    """Возвращает заголовок месяца и года."""

    if not dt:
        return "Без даты"
    month_name, _ = MONTH_NAMES_RU.get(dt.month, (dt.strftime("%B"), dt.strftime("%B")))
    return f"{month_name} {dt.year}"


def _format_entry(entry: dict, dt: datetime | None) -> str:
    """Форматирует одну запись взвешивания."""

    weight_value = html.escape(_format_weight(entry.get("weight")))

    if dt:
        _, month_genitive = MONTH_NAMES_RU.get(dt.month, (dt.strftime("%B"), dt.strftime("%B")))
        day_part = f"{dt.day} {month_genitive}"
        time_part = ""
        if dt.hour or dt.minute:
            time_part = f", {dt.strftime('%H:%M')}"
        date_part = f"{day_part}{time_part}"
    else:
        date_part = "Дата не указана"

    note = entry.get("note") or entry.get("comment")
    note_part = ""
    if note:
        note_part = f"\n📝 {html.escape(str(note))}"

    return f"• {date_part} — <code>{weight_value}</code> кг ⚖️{note_part}"


def _build_keyboard(page: int, total_pages: int) -> InlineKeyboardMarkup:
    """Создает клавиатуру для навигации по страницам."""

    keyboard: list[list[InlineKeyboardButton]] = []

    nav_row: list[InlineKeyboardButton] = []
    if page > 1:
        nav_row.append(
            InlineKeyboardButton("⬅️ Предыдущая", callback_data=f"weight_data_page_{page - 1}")
        )
    if page < total_pages:
        nav_row.append(
            InlineKeyboardButton("Следующая ➡️", callback_data=f"weight_data_page_{page + 1}")
        )
    if nav_row:
        keyboard.append(nav_row)

    keyboard.append([
        InlineKeyboardButton("⚙️ Назад к настройкам", callback_data="settings")
    ])

    return InlineKeyboardMarkup(keyboard)


def _format_history(items: Iterable[dict], page: int, total_pages: int, total_items: int) -> str:
    """Создает текст для отображения истории взвешиваний."""

    lines: list[str] = ["⚖️ <b>История взвешиваний</b>"]

    if total_items:
        lines.append("")
        lines.append(f"📦 Всего записей: <code>{total_items}</code>")
        lines.append(f"📄 Страница: <code>{page}</code> / <code>{total_pages}</code>")
        lines.append("")

        current_month: str | None = None
        for entry in items:
            dt = _parse_iso_datetime(
                entry.get("date")
                or entry.get("createdAt")
                or entry.get("created_at")
            )
            month_header = _format_month_header(dt)
            if month_header != current_month:
                if current_month is not None:
                    lines.append("")
                lines.append(f"📅 <b>{html.escape(month_header)}</b>")
                current_month = month_header
            lines.append(_format_entry(entry, dt))
        lines.append("")
        lines.append("✨ Продолжайте следить за прогрессом!")
        lines.append(
            "🧭 Кнопки «⬅️ Предыдущая» и «Следующая ➡️» перелистывают историю."
            " Вернуться к настройкам поможет «⚙️ Назад к настройкам»."
        )
    else:
        lines.append("")
        lines.append("📭 Записей взвешивания пока нет.")
        lines.append(
            "Добавьте первое измерение через меню «📋 Личные данные» → «Вес»."
            " Записи из режима Gym-Stat появятся здесь автоматически после"
            " синхронизации. 💪"
        )
        lines.append(
            "ℹ️ Если кнопки не реагируют, откройте раздел заново через"
            " «⚙️ Настройки» или выполните /login для повторной авторизации."
        )

    return "\n".join(lines)


async def show_weight_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отображает историю взвешиваний пользователя."""

    query = update.callback_query
    if not query:
        logger.error("Отсутствует callback_query при показе данных взвешивания")
        return ConversationHandler.END

    await query.answer()

    user_id = query.from_user.id
    page = _extract_page(query.data)

    logger.info("Пользователь %s запросил данные взвешиваний (страница %s)", user_id, page)

    try:
        mode = await get_user_mode(user_id)
    except Exception as exc:  # noqa: BLE001
        logger.error("Не удалось получить режим пользователя %s: %s", user_id, exc)
        try:
            await query.message.edit_text(
                "⚠️ Не удалось определить режим работы. Попробуйте позже.",
                reply_markup=get_settings_menu(),
            )
        except TelegramError as telegram_error:
            logger.error("Ошибка Telegram при отправке сообщения пользователю %s: %s", user_id, telegram_error)
        context.user_data['conversation_active'] = False
        return ConversationHandler.END

    if mode != "api":
        try:
            await query.message.edit_text(
                "ℹ️ История взвешиваний доступна только при подключении к Gym-Stat."
                " Используйте /login для входа.",
                reply_markup=get_settings_menu(),
            )
        except TelegramError as telegram_error:
            logger.error("Ошибка Telegram при отправке уведомления пользователю %s: %s", user_id, telegram_error)
        context.user_data['conversation_active'] = False
        return ConversationHandler.END

    token = await get_valid_access_token(user_id)
    if not token:
        try:
            await query.message.edit_text(
                "🔐 Требуется повторный вход. Используйте /login, чтобы продолжить.",
                reply_markup=get_settings_menu(),
            )
        except TelegramError as telegram_error:
            logger.error("Ошибка Telegram при уведомлении пользователя %s о входе: %s", user_id, telegram_error)
        context.user_data['conversation_active'] = False
        return ConversationHandler.END

    try:
        response = await api_get_weight_data(token, params={"orderBy": "date"})
    except httpx.HTTPError as exc:
        logger.error("Ошибка при запросе данных взвешивания пользователя %s: %s", user_id, exc)
        try:
            await query.message.edit_text(
                "❌ Не удалось получить данные взвешиваний. Попробуйте позже.",
                reply_markup=get_settings_menu(),
            )
        except TelegramError as telegram_error:
            logger.error("Ошибка Telegram при уведомлении пользователя %s: %s", user_id, telegram_error)
        context.user_data['conversation_active'] = False
        return ConversationHandler.END

    if response.status_code != 200:
        logger.warning(
            "Не удалось получить взвешивания для пользователя %s: %s %s",
            user_id,
            response.status_code,
            response.text,
        )
        try:
            await query.message.edit_text(
                "❌ Не удалось получить данные взвешиваний. Попробуйте позже.",
                reply_markup=get_settings_menu(),
            )
        except TelegramError as telegram_error:
            logger.error("Ошибка Telegram при отправке сообщения пользователю %s: %s", user_id, telegram_error)
        context.user_data['conversation_active'] = False
        return ConversationHandler.END

    try:
        payload = response.json()
    except ValueError:
        payload = []

    items = _normalize_items(payload)
    items.sort(
        key=lambda item: _parse_iso_datetime(
            item.get("date") or item.get("createdAt") or item.get("created_at")
        )
        or datetime.min,
        reverse=True,
    )

    total_items = len(items)
    total_pages = max(1, math.ceil(total_items / PAGE_SIZE)) if total_items else 1
    page = max(1, min(page, total_pages))
    start_index = (page - 1) * PAGE_SIZE
    end_index = start_index + PAGE_SIZE
    page_items = items[start_index:end_index]

    text = _format_history(page_items, page, total_pages, total_items)
    keyboard = _build_keyboard(page, total_pages)

    try:
        await query.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=keyboard,
        )
    except BadRequest as exc:
        if "Message is not modified" in str(exc):
            logger.debug("Сообщение данных взвешивания не изменилось для пользователя %s", user_id)
        else:
            logger.error("Ошибка Telegram при редактировании сообщения для пользователя %s: %s", user_id, exc)
    except TelegramError as exc:
        logger.error("Ошибка Telegram при отправке данных взвешивания пользователю %s: %s", user_id, exc)
        try:
            await query.message.reply_text(
                text,
                parse_mode="HTML",
                reply_markup=keyboard,
            )
        except TelegramError as reply_exc:
            logger.error("Не удалось отправить fallback-сообщение пользователю %s: %s", user_id, reply_exc)

    context.user_data['conversation_active'] = False
    return ConversationHandler.END