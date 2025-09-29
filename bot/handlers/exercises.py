"""Обработчики раздела "Мои упражнения" и управление группами упражнений."""

from __future__ import annotations

import html
import re
from datetime import datetime, timezone
from typing import Any, Iterable, Optional

import httpx
from telegram import Update
from telegram.error import TelegramError
from telegram.ext import ContextTypes, ConversationHandler

from bot.api.gym_stat_client import (
    create_exercise as api_create_exercise,
    create_exercise_group as api_create_exercise_group,
    delete_exercise as api_delete_exercise,
    delete_exercise_group as api_delete_exercise_group,
    get_exercise as api_get_exercise,
    get_exercise_groups as api_get_exercise_groups,
    get_exercises as api_get_exercises,
    update_exercise as api_update_exercise,
    update_exercise_group as api_update_exercise_group,
)
from bot.config.settings import (
    EXERCISE_GROUP_RENAME,
    EXERCISE_GROUP_SET_DESCRIPTION,
    EXERCISE_GROUP_SET_NAME,
    EXERCISE_GROUP_UPDATE_DESCRIPTION,
    EXERCISE_RENAME,
    EXERCISE_SET_DESCRIPTION,
    EXERCISE_SET_NAME,
    EXERCISE_UPDATE_DESCRIPTION,
)
from bot.keyboards.exercises_menu import (
    build_exercise_group_selection_keyboard,
    build_exercise_group_update_keyboard,
    build_exercise_groups_keyboard,
    build_exercises_keyboard,
    get_exercise_actions_keyboard,
    get_exercise_delete_keyboard,
    get_exercise_group_actions_keyboard,
    get_exercise_group_delete_keyboard,
    get_exercises_menu,
)
from bot.utils.api_session import get_valid_access_token
from bot.utils.db_utils import get_user_mode
from bot.utils.logger import setup_logging
from bot.utils.message_deletion import schedule_message_deletion


logger = setup_logging()

_PROMPT_KEY = "exercise_group_prompt"
_DRAFT_KEY = "exercise_group_draft"
_UUID_KEY = "exercise_group_uuid"
_CACHE_KEY = "exercise_groups_cache"
_EXERCISE_PROMPT_KEY = "exercise_prompt"
_EXERCISE_DRAFT_KEY = "exercise_draft"
_EXERCISE_UUID_KEY = "exercise_uuid"
_EXERCISE_CACHE_KEY = "exercises_cache"
_EXERCISE_GROUP_CHOICES_KEY = "exercise_group_choices"
_EXERCISE_GROUP_UPDATE_CHOICES_KEY = "exercise_group_update_choices"

EXERCISE_GROUPS_PAGE_SIZE = 5
_GROUPS_PAGE_KEY = "exercise_groups_page"


_USER_INPUT_DELETE_DELAY = 15


_DESCRIPTION_INTRO = (
    "🗂️ <b>Группы упражнений</b>\n"
    "Описание: Группы помогают объединять упражнения по категориям и быстрее находить их в тренировках.\n"
)

_EXERCISES_INTRO = (
    "📋 <b>Упражнения</b>\n"
    "Описание: Упражнения синхронизируются с Gym-Stat и привязаны к выбранным группам.\n"
)

_UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)

_DESCRIPTION_SOURCE_KEYS = (
    "description",
    "description_text",
    "descriptionText",
    "description_html",
    "descriptionHtml",
    "description_plain",
    "descriptionPlain",
    "notes",
    "note",
)

_NESTED_DESCRIPTION_KEYS = (
    "text",
    "value",
    "description",
    "content",
    "body",
    "plain",
    "plain_text",
    "plainText",
)


async def show_exercises_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Показывает раздел «Мои упражнения» с выбором дальнейших действий."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    mode = await get_user_mode(user_id)

    if mode == "api":
        details = (
            "Здесь вы можете управлять группами и упражнениями Gym-Stat: создавать новые элементы, обновлять их и удалять.\n"
            "Выберите нужный раздел ниже, чтобы перейти к списку упражнений или категорий."
        )
    else:
        details = (
            "Сейчас активен локальный режим. Для работы с упражнениями и группами подключите режим Gym-Stat через «🔄 Сменить режим».\n"
            "После авторизации появится возможность создавать категории и упражнения."
        )

    text = (
        "🗂️ <b>Мои упражнения</b>\n"
        "Раздел поможет структурировать тренировки и упражнения.\n\n"
        f"{details}"
    )

    await query.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=get_exercises_menu(),
    )
    context.user_data["conversation_active"] = False
    return ConversationHandler.END


async def show_exercises(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отображает список упражнений пользователя."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    mode = await get_user_mode(user_id)
    if mode != "api":
        await query.message.edit_text(
            (
                _EXERCISES_INTRO
                + "Управление упражнениями доступно только после переключения на режим Gym-Stat."
            ),
            parse_mode="HTML",
            reply_markup=get_exercises_menu(),
        )
        context.user_data["conversation_active"] = False
        return ConversationHandler.END

    token = await get_valid_access_token(user_id)
    if not token:
        await query.message.edit_text(
            (
                _EXERCISES_INTRO
                + "🔐 Для работы с упражнениями выполните вход через /login или кнопку «Войти»."
            ),
            parse_mode="HTML",
            reply_markup=get_exercises_menu(),
        )
        context.user_data["conversation_active"] = False
        return ConversationHandler.END

    exercises = await _fetch_exercises(context, user_id, token)
    if exercises is None:
        await query.message.edit_text(
            (
                _EXERCISES_INTRO
                + "❌ Не удалось получить данные с сервера. Попробуйте повторить попытку позже."
            ),
            parse_mode="HTML",
            reply_markup=get_exercises_menu(),
        )
        context.user_data["conversation_active"] = False
        return ConversationHandler.END

    await query.message.edit_text(
        _build_exercises_text(exercises),
        parse_mode="HTML",
        reply_markup=build_exercises_keyboard(exercises),
    )
    context.user_data["conversation_active"] = False
    return ConversationHandler.END


def _reset_flow(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Удаляет временные данные, связанные с управлением группами упражнений."""
    for key in (_PROMPT_KEY, _DRAFT_KEY, _UUID_KEY):
        context.user_data.pop(key, None)


def _reset_exercise_flow(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Удаляет временные данные, связанные с управлением упражнениями."""
    for key in (
        _EXERCISE_PROMPT_KEY,
        _EXERCISE_DRAFT_KEY,
        _EXERCISE_UUID_KEY,
        _EXERCISE_GROUP_CHOICES_KEY,
        _EXERCISE_GROUP_UPDATE_CHOICES_KEY,
    ):
        context.user_data.pop(key, None)


async def _safe_edit_message(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    message_id: int,
    *,
    text: str,
    reply_markup=None,
) -> None:
    """Безопасно редактирует сообщение, подавляя ошибки Telegram API."""
    try:
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=text,
            parse_mode="HTML",
            reply_markup=reply_markup,
        )
    except TelegramError as exc:
        logger.warning("Не удалось отредактировать сообщение %s: %s", message_id, exc)


def _filter_groups(payload: Any) -> list[dict]:
    """Преобразует ответ API к списку словарей с группами."""
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("data", "results", "items", "records"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        if payload.get("uuid"):
            return [payload]
    return []


def _find_group(groups: Iterable[dict], uuid: str) -> Optional[dict]:
    for group in groups:
        if isinstance(group, dict) and group.get("uuid") == uuid:
            return group
    return None


def _format_datetime(value: Any) -> Optional[str]:
    dt = _parse_datetime(value)
    if not dt:
        return None
    return dt.strftime("%d.%m.%Y %H:%M")


def _parse_datetime(value: Any) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str):
        normalized = value.strip().replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(normalized)
        except ValueError:
            return None
    else:
        return None
    if dt.tzinfo:
        dt = dt.astimezone(timezone.utc)
    else:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _extract_readable_text(value: Any) -> Optional[str]:
    if isinstance(value, str):
        text = value.strip()
        if not text or _UUID_PATTERN.fullmatch(text):
            return None
        return text
    if isinstance(value, dict):
        for key in _NESTED_DESCRIPTION_KEYS:
            if key in value:
                nested = _extract_readable_text(value.get(key))
                if nested:
                    return nested
        for nested in value.values():
            text = _extract_readable_text(nested)
            if text:
                return text
        return None
    if isinstance(value, (list, tuple, set)):
        for item in value:
            text = _extract_readable_text(item)
            if text:
                return text
    return None


def _get_description_text(entity: dict) -> str:
    for key in _DESCRIPTION_SOURCE_KEYS:
        text = _extract_readable_text(entity.get(key))
        if text:
            return text
    for key, value in entity.items():
        if isinstance(key, str) and "desc" in key.lower():
            text = _extract_readable_text(value)
            if text:
                return text
    return ""


def _format_group_details(group: dict) -> str:
    name = html.escape(str(group.get("name") or "Без названия"))
    description_text = _get_description_text(group)
    description = html.escape(description_text) if description_text else "—"
    uuid = html.escape(str(group.get("uuid") or "—"))
    created = _format_datetime(group.get("createdAt") or group.get("created_at"))
    updated = _format_datetime(group.get("updatedAt") or group.get("updated_at"))

    lines = [
        f"🗂️ <b>{name}</b>",
        f"Описание: {description}",
    ]
    if created:
        lines.append(f"Создано: {created}")
    if updated:
        lines.append(f"Обновлено: {updated}")
    lines.append(
        "\nИспользуйте кнопки ниже, чтобы переименовать группу, обновить описание или удалить её."
    )
    return "\n".join(lines)


def _build_groups_text(
    groups: Iterable[dict], *, page: int, total_pages: int
) -> str:
    groups_list = list(groups)
    if groups_list:
        return (
            _DESCRIPTION_INTRO
            + f'\n\n'
            + f"📘 Страница {page} из {total_pages}.\n"
            + "Выберите группу, чтобы посмотреть детали или изменить её параметры."
        )
    return (
        _DESCRIPTION_INTRO
        + "Пока у вас нет групп упражнений. Нажмите «➕ Создать группу», чтобы добавить первую."
    )


def _parse_groups_page(callback_data: str) -> int:
    if callback_data == "exercise_groups":
        return 1
    if callback_data.startswith("exercise_groups:page:"):
        try:
            value = int(callback_data.rsplit(":", 1)[-1])
        except ValueError:
            return 1
        return value if value > 0 else 1
    return 1


def _coerce_page(value: Any) -> int:
    if isinstance(value, int):
        return value if value > 0 else 1
    if isinstance(value, str) and value.isdigit():
        numeric = int(value)
        return numeric if numeric > 0 else 1
    return 1


def _get_current_groups_page(context: ContextTypes.DEFAULT_TYPE) -> int:
    return _coerce_page(context.user_data.get(_GROUPS_PAGE_KEY, 1))


def _sort_groups(groups: Iterable[dict]) -> list[dict]:
    def _group_sort_key(group: dict) -> datetime:
        updated = _parse_datetime(
            group.get("updatedAt")
            or group.get("updated_at")
            or group.get("modifiedAt")
            or group.get("modified_at")
        )
        created = _parse_datetime(group.get("createdAt") or group.get("created_at"))
        timestamp = updated or created
        if timestamp is None:
            timestamp = datetime.min.replace(tzinfo=timezone.utc)
        return timestamp

    sorted_groups = [group for group in groups if isinstance(group, dict)]
    sorted_groups.sort(key=_group_sort_key, reverse=True)
    return sorted_groups


def _paginate_groups(groups: list[dict], page: int) -> tuple[list[dict], int, int]:
    if not groups:
        return [], 1, 1

    total_pages = (len(groups) + EXERCISE_GROUPS_PAGE_SIZE - 1) // EXERCISE_GROUPS_PAGE_SIZE
    page = max(1, min(page, total_pages))
    start = (page - 1) * EXERCISE_GROUPS_PAGE_SIZE
    end = start + EXERCISE_GROUPS_PAGE_SIZE
    return groups[start:end], page, total_pages


async def _fetch_groups(
    context: ContextTypes.DEFAULT_TYPE,
    user_id: int,
    token: str,
) -> Optional[list[dict]]:
    try:
        response = await api_get_exercise_groups(token)
    except httpx.RequestError as exc:
        logger.error("Ошибка запроса списка групп для пользователя %s: %s", user_id, exc)
        return None

    if response.status_code != 200:
        logger.warning(
            "Не удалось получить группы упражнений (%s): %s",
            response.status_code,
            response.text,
        )
        return None

    groups = _sort_groups(_filter_groups(response.json() or []))
    context.user_data[_CACHE_KEY] = groups
    return groups


def _filter_exercises(payload: Any) -> list[dict]:
    """Преобразует ответ API в список упражнений."""
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("data", "results", "items", "records"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        if payload.get("uuid"):
            return [payload]
    return []


def _find_exercise(exercises: Iterable[dict], uuid: str) -> Optional[dict]:
    for exercise in exercises:
        if isinstance(exercise, dict) and exercise.get("uuid") == uuid:
            return exercise
    return None


def _format_exercise_details(exercise: dict) -> str:
    name = html.escape(str(exercise.get("name") or "Без названия"))
    description_text = _get_description_text(exercise)
    description = html.escape(description_text) if description_text else "—"
    group = exercise.get("exerciseGroup") or exercise.get("group") or {}

    if not isinstance(group, dict):
        group = {}
    group_name = html.escape(str(group.get("name") or "Не выбрана"))

    created = _format_datetime(exercise.get("createdAt") or exercise.get("created_at"))
    updated = _format_datetime(exercise.get("updatedAt") or exercise.get("updated_at"))

    lines = [
        f"📋 <b>{name}</b>",
        f"Описание: {description}",
    ]

    group_line = f"Группа: {group_name}"
    lines.append(group_line)

    if created:
        lines.append(f"Создано: {created}")
    if updated:
        lines.append(f"Обновлено: {updated}")

    lines.append(
        "\nИспользуйте кнопки ниже, чтобы изменить название, описание, группу или удалить упражнение."
    )
    return "\n".join(lines)


def _build_exercises_text(exercises: Iterable[dict]) -> str:
    exercises_list = list(exercises)
    if exercises_list:
        return (
            _EXERCISES_INTRO
            + "Выберите упражнение, чтобы посмотреть детали или изменить его параметры."
        )
    return (
        _EXERCISES_INTRO
        + "Пока у вас нет упражнений. Нажмите «➕ Создать упражнение», чтобы добавить первое."
    )


async def _fetch_exercises(
    context: ContextTypes.DEFAULT_TYPE,
    user_id: int,
    token: str,
) -> Optional[list[dict]]:
    try:
        response = await api_get_exercises(token)
    except httpx.RequestError as exc:
        logger.error("Ошибка запроса списка упражнений для пользователя %s: %s", user_id, exc)
        return None

    if response.status_code != 200:
        logger.warning(
            "Не удалось получить упражнения (%s): %s",
            response.status_code,
            response.text,
        )
        return None

    exercises = _filter_exercises(response.json() or [])
    context.user_data[_EXERCISE_CACHE_KEY] = exercises
    return exercises


async def _fetch_exercise(
    context: ContextTypes.DEFAULT_TYPE,
    user_id: int,
    token: str,
    uuid: str,
) -> Optional[dict]:
    try:
        response = await api_get_exercise(token, uuid)
    except httpx.RequestError as exc:
        logger.error("Ошибка запроса упражнения %s для пользователя %s: %s", uuid, user_id, exc)
        return None

    if response.status_code != 200:
        logger.warning(
            "Не удалось получить упражнение %s (%s): %s",
            uuid,
            response.status_code,
            response.text,
        )
        return None

    payload = response.json() or {}
    if not isinstance(payload, dict):
        return None

    exercises = context.user_data.get(_EXERCISE_CACHE_KEY)
    if isinstance(exercises, list):
        updated = [item for item in exercises if isinstance(item, dict) and item.get("uuid") != uuid]
        updated.append(payload)
        context.user_data[_EXERCISE_CACHE_KEY] = updated

    return payload


async def show_exercise_details(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отображает подробности выбранного упражнения."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data or ""
    parts = data.split(":", 2)
    uuid = parts[2] if len(parts) == 3 else ""

    mode = await get_user_mode(user_id)
    if mode != "api":
        await query.message.edit_text(
            (
                _EXERCISES_INTRO
                + "Просмотр упражнений доступен только в режиме Gym-Stat."
            ),
            parse_mode="HTML",
            reply_markup=get_exercises_menu(),
        )
        context.user_data["conversation_active"] = False
        return ConversationHandler.END

    token = await get_valid_access_token(user_id)
    if not token:
        await query.message.edit_text(
            (
                _EXERCISES_INTRO
                + "🔐 Авторизуйтесь через /login, чтобы просматривать упражнения."
            ),
            parse_mode="HTML",
            reply_markup=get_exercises_menu(),
        )
        context.user_data["conversation_active"] = False
        return ConversationHandler.END

    exercises = context.user_data.get(_EXERCISE_CACHE_KEY, []) or []
    exercise = _find_exercise(exercises, uuid)
    if exercise is None:
        exercise = await _fetch_exercise(context, user_id, token, uuid)
        if exercise is None:
            exercises = await _fetch_exercises(context, user_id, token) or []
            await query.message.edit_text(
                (
                    _EXERCISES_INTRO
                    + "⚠️ Не удалось найти выбранное упражнение. Возможно, оно было удалено."
                ),
                parse_mode="HTML",
                reply_markup=build_exercises_keyboard(exercises),
            )
            context.user_data["conversation_active"] = False
            return ConversationHandler.END

    context.user_data[_EXERCISE_UUID_KEY] = uuid
    await query.message.edit_text(
        _format_exercise_details(exercise),
        parse_mode="HTML",
        reply_markup=get_exercise_actions_keyboard(uuid),
    )
    context.user_data["conversation_active"] = False
    return ConversationHandler.END


async def prompt_create_exercise(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Запрашивает данные для создания нового упражнения."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    mode = await get_user_mode(user_id)
    if mode != "api":
        await query.message.edit_text(
            (
                _EXERCISES_INTRO
                + "Переключитесь на режим Gym-Stat, чтобы добавлять упражнения."
            ),
            parse_mode="HTML",
            reply_markup=get_exercises_menu(),
        )
        context.user_data["conversation_active"] = False
        return ConversationHandler.END

    token = await get_valid_access_token(user_id)
    if not token:
        await query.message.edit_text(
            (
                _EXERCISES_INTRO
                + "🔐 Авторизуйтесь через /login, чтобы создавать упражнения."
            ),
            parse_mode="HTML",
            reply_markup=get_exercises_menu(),
        )
        context.user_data["conversation_active"] = False
        return ConversationHandler.END

    groups = await _fetch_groups(context, user_id, token)
    if groups is None:
        await query.message.edit_text(
            (
                _EXERCISES_INTRO
                + "❌ Не удалось получить список групп. Попробуйте позже."
            ),
            parse_mode="HTML",
            reply_markup=get_exercises_menu(),
        )
        context.user_data["conversation_active"] = False
        return ConversationHandler.END
    if not groups:
        await query.message.edit_text(
            (
                _EXERCISES_INTRO
                + "⚠️ Чтобы создать упражнение, сначала добавьте группу в разделе «Группы упражнений»."
            ),
            parse_mode="HTML",
            reply_markup=get_exercises_menu(),
        )
        context.user_data["conversation_active"] = False
        return ConversationHandler.END

    context.user_data[_EXERCISE_PROMPT_KEY] = (query.message.chat_id, query.message.message_id)
    context.user_data[_EXERCISE_DRAFT_KEY] = {}

    await query.message.edit_text(
        (
            "✍️ <b>Введите название упражнения</b>\n"
            "Например: <code>Жим лёжа</code>. /cancel — отмена."
        ),
        parse_mode="HTML",
    )
    context.user_data["conversation_active"] = True
    return EXERCISE_SET_NAME


async def handle_exercise_name_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает ввод названия упражнения."""
    message = update.message
    if not message or not message.text:
        return EXERCISE_SET_NAME

    name = message.text.strip()
    user_chat_id = message.chat_id
    user_message_id = message.message_id
    if not name:
        warning_message = await message.reply_text(
            "⚠️ Название не может быть пустым. Укажите другое значение."
        )
        schedule_message_deletion(
            context,
            [user_message_id, warning_message.message_id],
            user_chat_id,
            delay=_USER_INPUT_DELETE_DELAY,
        )
        return EXERCISE_SET_NAME

    draft = context.user_data.get(_EXERCISE_DRAFT_KEY)
    if not isinstance(draft, dict):
        draft = {}
    draft["name"] = name
    context.user_data[_EXERCISE_DRAFT_KEY] = draft

    prompt = context.user_data.get(_EXERCISE_PROMPT_KEY)
    text = (
        "✍️ <b>Введите описание упражнения</b>\n"
        "Можно указать краткую подсказку. Отправьте «-», чтобы оставить пустым."
    )
    if prompt:
        prompt_chat_id, message_id = prompt
        await _safe_edit_message(context, prompt_chat_id, message_id, text=text)
    else:
        prompt_message = await message.reply_text(text, parse_mode="HTML")
        schedule_message_deletion(
            context,
            [prompt_message.message_id],
            user_chat_id,
            delay=_USER_INPUT_DELETE_DELAY,
        )

    schedule_message_deletion(
        context,
        [user_message_id],
        user_chat_id,
        delay=_USER_INPUT_DELETE_DELAY,
    )

    context.user_data["conversation_active"] = True
    return EXERCISE_SET_DESCRIPTION


async def handle_exercise_description_input(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Сохраняет описание и предлагает выбрать группу."""
    message = update.message
    if not message or message.text is None:
        return EXERCISE_SET_DESCRIPTION

    description = message.text.strip()
    if description == "-":
        description = ""

    user_chat_id = message.chat_id
    user_message_id = message.message_id
    draft = context.user_data.get(_EXERCISE_DRAFT_KEY)
    name = draft.get("name") if isinstance(draft, dict) else None
    if not name:
        warning_message = await message.reply_text(
            "⚠️ Не удалось определить название упражнения. Попробуйте снова."
        )
        schedule_message_deletion(
            context,
            [user_message_id, warning_message.message_id],
            user_chat_id,
            delay=_USER_INPUT_DELETE_DELAY,
        )
        _reset_exercise_flow(context)
        context.user_data["conversation_active"] = False
        return ConversationHandler.END

    user_id = message.from_user.id
    mode = await get_user_mode(user_id)
    if mode != "api":
        info_message = await message.reply_text(
            "Для создания упражнений необходимо включить режим Gym-Stat."
        )
        schedule_message_deletion(
            context,
            [user_message_id, info_message.message_id],
            user_chat_id,
            delay=_USER_INPUT_DELETE_DELAY,
        )
        _reset_exercise_flow(context)
        context.user_data["conversation_active"] = False
        return ConversationHandler.END

    token = await get_valid_access_token(user_id)
    if not token:
        info_message = await message.reply_text(
            "🔐 Пожалуйста, выполните вход через /login и повторите попытку."
        )
        schedule_message_deletion(
            context,
            [user_message_id, info_message.message_id],
            user_chat_id,
            delay=_USER_INPUT_DELETE_DELAY,
        )
        _reset_exercise_flow(context)
        context.user_data["conversation_active"] = False
        return ConversationHandler.END

    draft["description"] = description
    context.user_data[_EXERCISE_DRAFT_KEY] = draft

    groups = context.user_data.get(_CACHE_KEY)
    if not isinstance(groups, list) or not groups:
        groups = await _fetch_groups(context, user_id, token)
        if groups is None:
            error_message = await message.reply_text(
                "❌ Не удалось получить список групп. Попробуйте позже."
            )
            schedule_message_deletion(
                context,
                [user_message_id, error_message.message_id],
                user_chat_id,
                delay=_USER_INPUT_DELETE_DELAY,
            )
            _reset_exercise_flow(context)
            context.user_data["conversation_active"] = False
            return ConversationHandler.END
        if not groups:
            info_message = await message.reply_text(
                "⚠️ Прежде чем создать упражнение, добавьте хотя бы одну группу в разделе «Группы упражнений»."
            )
            schedule_message_deletion(
                context,
                [user_message_id, info_message.message_id],
                user_chat_id,
                delay=_USER_INPUT_DELETE_DELAY,
            )
            _reset_exercise_flow(context)
            context.user_data["conversation_active"] = False
            return ConversationHandler.END

    context.user_data[_EXERCISE_GROUP_CHOICES_KEY] = {
        str(index): group.get("uuid")
        for index, group in enumerate(groups)
        if isinstance(group, dict) and group.get("uuid")
    }

    prompt = context.user_data.get(_EXERCISE_PROMPT_KEY)
    text = (
        "📂 <b>Выберите группу для упражнения</b>\n"
        "Нажмите на подходящую категорию ниже. Если нужной группы нет, сначала создайте её."
    )
    if prompt:
        chat_id, message_id = prompt
        await _safe_edit_message(
            context,
            chat_id,
            message_id,
            text=text,
            reply_markup=build_exercise_group_selection_keyboard(groups),
        )
    else:
        await message.reply_text(
            text,
            parse_mode="HTML",
            reply_markup=build_exercise_group_selection_keyboard(groups),
        )

    schedule_message_deletion(
        context,
        [user_message_id],
        user_chat_id,
        delay=_USER_INPUT_DELETE_DELAY,
    )

    context.user_data["conversation_active"] = False
    return ConversationHandler.END


async def handle_exercise_group_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Создаёт упражнение после выбора группы."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data or ""
    if data.startswith("exercise:select_group:create:"):
        group_uuid = data.rsplit(":", 1)[-1]
    else:
        parts = data.split(":", 2)
        choice_key = parts[2] if len(parts) >= 3 else ""
        choices = context.user_data.get(_EXERCISE_GROUP_CHOICES_KEY, {}) or {}
        group_uuid = choices.get(choice_key, "")

    draft = context.user_data.get(_EXERCISE_DRAFT_KEY)
    name = draft.get("name") if isinstance(draft, dict) else None
    description = draft.get("description") if isinstance(draft, dict) else ""

    if not name or not group_uuid:
        await query.message.edit_text(
            (
                _EXERCISES_INTRO
                + "⚠️ Не удалось определить данные упражнения. Повторите создание ещё раз."
            ),
            parse_mode="HTML",
            reply_markup=get_exercises_menu(),
        )
        _reset_exercise_flow(context)
        context.user_data["conversation_active"] = False
        return ConversationHandler.END

    mode = await get_user_mode(user_id)
    if mode != "api":
        await query.message.edit_text(
            (
                _EXERCISES_INTRO
                + "Создание упражнений доступно только в режиме Gym-Stat."
            ),
            parse_mode="HTML",
            reply_markup=get_exercises_menu(),
        )
        _reset_exercise_flow(context)
        context.user_data["conversation_active"] = False
        return ConversationHandler.END

    token = await get_valid_access_token(user_id)
    if not token:
        await query.message.edit_text(
            (
                _EXERCISES_INTRO
                + "🔐 Авторизуйтесь через /login, чтобы создавать упражнения."
            ),
            parse_mode="HTML",
            reply_markup=get_exercises_menu(),
        )
        _reset_exercise_flow(context)
        context.user_data["conversation_active"] = False
        return ConversationHandler.END

    payload = {
        "name": name,
        "description": description,
        "exerciseGroupId": group_uuid,
    }

    try:
        response = await api_create_exercise(token, payload)
    except httpx.RequestError as exc:
        logger.error("Ошибка создания упражнения для пользователя %s: %s", user_id, exc)
        await query.message.edit_text(
            _EXERCISES_INTRO + "❌ Не удалось создать упражнение. Попробуйте позже.",
            parse_mode="HTML",
            reply_markup=get_exercises_menu(),
        )
        _reset_exercise_flow(context)
        context.user_data["conversation_active"] = False
        return ConversationHandler.END

    if response.status_code not in (200, 201):
        logger.warning(
            "Ошибка API при создании упражнения (%s): %s",
            response.status_code,
            response.text,
        )
        await query.message.edit_text(
            _EXERCISES_INTRO + "❌ Gym-Stat вернул ошибку при создании упражнения.",
            parse_mode="HTML",
            reply_markup=get_exercises_menu(),
        )
        _reset_exercise_flow(context)
        context.user_data["conversation_active"] = False
        return ConversationHandler.END

    exercises = await _fetch_exercises(context, user_id, token) or []

    prompt = context.user_data.get(_EXERCISE_PROMPT_KEY)
    if prompt:
        chat_id, message_id = prompt
        await _safe_edit_message(
            context,
            chat_id,
            message_id,
            text=_build_exercises_text(exercises),
            reply_markup=build_exercises_keyboard(exercises),
        )
    else:
        await query.message.edit_text(
            _build_exercises_text(exercises),
            parse_mode="HTML",
            reply_markup=build_exercises_keyboard(exercises),
        )

    _reset_exercise_flow(context)
    context.user_data["conversation_active"] = False
    return ConversationHandler.END


async def handle_exercise_creation_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отменяет создание упражнения и возвращает список."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    _reset_exercise_flow(context)

    mode = await get_user_mode(user_id)
    if mode != "api":
        await query.message.edit_text(
            (
                _EXERCISES_INTRO
                + "Управление упражнениями доступно только в режиме Gym-Stat."
            ),
            parse_mode="HTML",
            reply_markup=get_exercises_menu(),
        )
        context.user_data["conversation_active"] = False
        return ConversationHandler.END

    token = await get_valid_access_token(user_id)
    if not token:
        await query.message.edit_text(
            (
                _EXERCISES_INTRO
                + "🔐 Для работы с упражнениями выполните вход через /login."
            ),
            parse_mode="HTML",
            reply_markup=get_exercises_menu(),
        )
        context.user_data["conversation_active"] = False
        return ConversationHandler.END

    exercises = await _fetch_exercises(context, user_id, token)
    if exercises is None:
        await query.message.edit_text(
            _EXERCISES_INTRO + "❌ Не удалось обновить список упражнений. Попробуйте позже.",
            parse_mode="HTML",
            reply_markup=get_exercises_menu(),
        )
        context.user_data["conversation_active"] = False
        return ConversationHandler.END

    await query.message.edit_text(
        _build_exercises_text(exercises),
        parse_mode="HTML",
        reply_markup=build_exercises_keyboard(exercises),
    )
    context.user_data["conversation_active"] = False
    return ConversationHandler.END


async def prompt_rename_exercise(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Запрашивает новое название для упражнения."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data or ""
    parts = data.split(":", 2)
    uuid = parts[2] if len(parts) == 3 else ""

    mode = await get_user_mode(user_id)
    if mode != "api":
        await query.message.edit_text(
            _EXERCISES_INTRO + "Переименовать упражнение можно только в режиме Gym-Stat.",
            parse_mode="HTML",
            reply_markup=get_exercises_menu(),
        )
        context.user_data["conversation_active"] = False
        return ConversationHandler.END

    token = await get_valid_access_token(user_id)
    if not token:
        await query.message.edit_text(
            _EXERCISES_INTRO + "🔐 Авторизуйтесь в Gym-Stat, чтобы редактировать упражнения.",
            parse_mode="HTML",
            reply_markup=get_exercises_menu(),
        )
        context.user_data["conversation_active"] = False
        return ConversationHandler.END

    context.user_data[_EXERCISE_UUID_KEY] = uuid
    context.user_data[_EXERCISE_PROMPT_KEY] = (query.message.chat_id, query.message.message_id)

    await query.message.edit_text(
        (
            "✏️ <b>Введите новое название упражнения</b>\n"
            "Отправьте /cancel, чтобы выйти без изменений."
        ),
        parse_mode="HTML",
    )
    context.user_data["conversation_active"] = True
    return EXERCISE_RENAME


async def handle_exercise_rename_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обновляет название упражнения."""
    message = update.message
    if not message or not message.text:
        return EXERCISE_RENAME

    new_name = message.text.strip()
    if not new_name:
        await message.reply_text("⚠️ Название не может быть пустым.")
        return EXERCISE_RENAME

    uuid = context.user_data.get(_EXERCISE_UUID_KEY)
    if not uuid:
        await message.reply_text("⚠️ Не удалось определить упражнение. Попробуйте снова.")
        _reset_exercise_flow(context)
        context.user_data["conversation_active"] = False
        return ConversationHandler.END

    user_id = message.from_user.id
    mode = await get_user_mode(user_id)
    if mode != "api":
        await message.reply_text("Переименование доступно только в режиме Gym-Stat.")
        _reset_exercise_flow(context)
        context.user_data["conversation_active"] = False
        return ConversationHandler.END

    token = await get_valid_access_token(user_id)
    if not token:
        await message.reply_text("🔐 Авторизуйтесь через /login и повторите попытку.")
        _reset_exercise_flow(context)
        context.user_data["conversation_active"] = False
        return ConversationHandler.END

    try:
        response = await api_update_exercise(token, uuid, {"name": new_name})
    except httpx.RequestError as exc:
        logger.error("Ошибка обновления названия упражнения %s: %s", uuid, exc)
        await message.reply_text("❌ Не удалось обновить название. Попробуйте позже.")
        _reset_exercise_flow(context)
        context.user_data["conversation_active"] = False
        return ConversationHandler.END

    if response.status_code not in (200, 204):
        logger.warning(
            "Ошибка API при переименовании упражнения (%s): %s",
            response.status_code,
            response.text,
        )
        await message.reply_text("❌ Gym-Stat вернул ошибку при переименовании упражнения.")
        _reset_exercise_flow(context)
        context.user_data["conversation_active"] = False
        return ConversationHandler.END

    prompt = context.user_data.get(_EXERCISE_PROMPT_KEY)
    chat_id, message_id = prompt if prompt else (message.chat_id, None)

    exercises = await _fetch_exercises(context, user_id, token) or []
    exercise = _find_exercise(exercises, uuid) or {"uuid": uuid, "name": new_name}

    text = _format_exercise_details(exercise)
    markup = get_exercise_actions_keyboard(uuid)

    if message_id is not None:
        await _safe_edit_message(context, chat_id, message_id, text=text, reply_markup=markup)
    else:
        await message.reply_text(text, parse_mode="HTML", reply_markup=markup)

    _reset_exercise_flow(context)
    context.user_data["conversation_active"] = False
    return ConversationHandler.END


async def prompt_change_exercise_description(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Запрашивает новое описание для упражнения."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data or ""
    parts = data.split(":", 2)
    uuid = parts[2] if len(parts) == 3 else ""

    mode = await get_user_mode(user_id)
    if mode != "api":
        await query.message.edit_text(
            _EXERCISES_INTRO + "Редактирование описания доступно только в режиме Gym-Stat.",
            parse_mode="HTML",
            reply_markup=get_exercises_menu(),
        )
        context.user_data["conversation_active"] = False
        return ConversationHandler.END

    token = await get_valid_access_token(user_id)
    if not token:
        await query.message.edit_text(
            _EXERCISES_INTRO + "🔐 Авторизуйтесь, чтобы редактировать упражнения.",
            parse_mode="HTML",
            reply_markup=get_exercises_menu(),
        )
        context.user_data["conversation_active"] = False
        return ConversationHandler.END

    context.user_data[_EXERCISE_UUID_KEY] = uuid
    context.user_data[_EXERCISE_PROMPT_KEY] = (query.message.chat_id, query.message.message_id)

    await query.message.edit_text(
        (
            "📝 <b>Введите новое описание упражнения</b>\n"
            "Отправьте «-», чтобы очистить описание. /cancel — отмена."
        ),
        parse_mode="HTML",
    )
    context.user_data["conversation_active"] = True
    return EXERCISE_UPDATE_DESCRIPTION


async def handle_exercise_description_update(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Обновляет описание упражнения."""
    message = update.message
    if not message or message.text is None:
        return EXERCISE_UPDATE_DESCRIPTION

    description = message.text.strip()
    if description == "-":
        description = ""

    uuid = context.user_data.get(_EXERCISE_UUID_KEY)
    if not uuid:
        await message.reply_text("⚠️ Не удалось определить упражнение. Попробуйте снова.")
        _reset_exercise_flow(context)
        context.user_data["conversation_active"] = False
        return ConversationHandler.END

    user_id = message.from_user.id
    mode = await get_user_mode(user_id)
    if mode != "api":
        await message.reply_text("Редактирование доступно только в режиме Gym-Stat.")
        _reset_exercise_flow(context)
        context.user_data["conversation_active"] = False
        return ConversationHandler.END

    token = await get_valid_access_token(user_id)
    if not token:
        await message.reply_text("🔐 Авторизуйтесь через /login и повторите попытку.")
        _reset_exercise_flow(context)
        context.user_data["conversation_active"] = False
        return ConversationHandler.END

    try:
        response = await api_update_exercise(token, uuid, {"description": description})
    except httpx.RequestError as exc:
        logger.error("Ошибка обновления описания упражнения %s: %s", uuid, exc)
        await message.reply_text("❌ Не удалось обновить описание. Попробуйте позже.")
        _reset_exercise_flow(context)
        context.user_data["conversation_active"] = False
        return ConversationHandler.END

    if response.status_code not in (200, 204):
        logger.warning(
            "Ошибка API при обновлении описания упражнения (%s): %s",
            response.status_code,
            response.text,
        )
        await message.reply_text("❌ Gym-Stat вернул ошибку при обновлении описания.")
        _reset_exercise_flow(context)
        context.user_data["conversation_active"] = False
        return ConversationHandler.END

    prompt = context.user_data.get(_EXERCISE_PROMPT_KEY)
    chat_id, message_id = prompt if prompt else (message.chat_id, None)

    exercises = await _fetch_exercises(context, user_id, token) or []
    exercise = _find_exercise(exercises, uuid) or {"uuid": uuid, "description": description}

    text = _format_exercise_details(exercise)
    markup = get_exercise_actions_keyboard(uuid)

    if message_id is not None:
        await _safe_edit_message(context, chat_id, message_id, text=text, reply_markup=markup)
    else:
        await message.reply_text(text, parse_mode="HTML", reply_markup=markup)

    _reset_exercise_flow(context)
    context.user_data["conversation_active"] = False
    return ConversationHandler.END


async def prompt_change_exercise_group(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Предлагает выбрать новую группу для упражнения."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data or ""
    parts = data.split(":", 2)
    uuid = parts[2] if len(parts) == 3 else ""

    mode = await get_user_mode(user_id)
    if mode != "api":
        await query.message.edit_text(
            _EXERCISES_INTRO + "Смена группы доступна только в режиме Gym-Stat.",
            parse_mode="HTML",
            reply_markup=get_exercises_menu(),
        )
        context.user_data["conversation_active"] = False
        return ConversationHandler.END

    token = await get_valid_access_token(user_id)
    if not token:
        await query.message.edit_text(
            _EXERCISES_INTRO + "🔐 Авторизуйтесь, чтобы редактировать упражнения.",
            parse_mode="HTML",
            reply_markup=get_exercises_menu(),
        )
        context.user_data["conversation_active"] = False
        return ConversationHandler.END

    exercises = context.user_data.get(_EXERCISE_CACHE_KEY, []) or []
    exercise = _find_exercise(exercises, uuid)
    if exercise is None:
        exercise = await _fetch_exercise(context, user_id, token, uuid)

    groups = await _fetch_groups(context, user_id, token)
    if groups is None:
        message_text = (
            _format_exercise_details(exercise)
            if exercise
            else _EXERCISES_INTRO + "❌ Не удалось получить список групп. Попробуйте позже."
        )
        markup = (
            get_exercise_actions_keyboard(uuid)
            if exercise
            else get_exercises_menu()
        )
        await query.message.edit_text(message_text, parse_mode="HTML", reply_markup=markup)
        context.user_data["conversation_active"] = False
        return ConversationHandler.END

    if not groups:
        message_text = (
            (_format_exercise_details(exercise) + "\n\n⚠️ Добавьте хотя бы одну группу, чтобы сменить категорию.")
            if exercise
            else _EXERCISES_INTRO
            + "⚠️ Добавьте хотя бы одну группу упражнений, чтобы можно было изменить категорию."
        )
        markup = (
            get_exercise_actions_keyboard(uuid)
            if exercise
            else get_exercises_menu()
        )
        await query.message.edit_text(message_text, parse_mode="HTML", reply_markup=markup)
        context.user_data["conversation_active"] = False
        return ConversationHandler.END

    context.user_data[_EXERCISE_UUID_KEY] = uuid
    context.user_data[_EXERCISE_PROMPT_KEY] = (query.message.chat_id, query.message.message_id)
    context.user_data[_EXERCISE_GROUP_UPDATE_CHOICES_KEY] = {
        str(index): group.get("uuid")
        for index, group in enumerate(groups)
        if isinstance(group, dict) and group.get("uuid")
    }

    await query.message.edit_text(
        (
            "📂 <b>Выберите новую группу для упражнения</b>\n"
            "Нажмите на подходящую категорию ниже."
        ),
        parse_mode="HTML",
        reply_markup=build_exercise_group_update_keyboard(uuid, groups),
    )
    context.user_data["conversation_active"] = False
    return ConversationHandler.END


async def handle_exercise_group_update_selection(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Меняет группу упражнения после выбора категории."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data or ""
    if data.startswith("exercise:select_group:update:"):
        parts = data.split(":", 4)
        exercise_uuid = parts[3] if len(parts) >= 4 else ""
        group_uuid = parts[4] if len(parts) >= 5 else ""
    else:
        parts = data.split(":", 2)
        choice_key = parts[2] if len(parts) >= 3 else ""
        exercise_uuid = context.user_data.get(_EXERCISE_UUID_KEY, "")
        update_choices = context.user_data.get(_EXERCISE_GROUP_UPDATE_CHOICES_KEY, {}) or {}
        group_uuid = update_choices.get(choice_key, "")

    if not exercise_uuid or not group_uuid:
        await query.message.edit_text(
            _EXERCISES_INTRO + "⚠️ Не удалось определить выбранные значения. Попробуйте снова.",
            parse_mode="HTML",
            reply_markup=get_exercises_menu(),
        )
        context.user_data["conversation_active"] = False
        return ConversationHandler.END

    mode = await get_user_mode(user_id)
    if mode != "api":
        await query.message.edit_text(
            _EXERCISES_INTRO + "Смена группы доступна только в режиме Gym-Stat.",
            parse_mode="HTML",
            reply_markup=get_exercises_menu(),
        )
        context.user_data["conversation_active"] = False
        return ConversationHandler.END

    token = await get_valid_access_token(user_id)
    if not token:
        await query.message.edit_text(
            _EXERCISES_INTRO + "🔐 Авторизуйтесь через /login, чтобы управлять упражнениями.",
            parse_mode="HTML",
            reply_markup=get_exercises_menu(),
        )
        context.user_data["conversation_active"] = False
        return ConversationHandler.END

    try:
        response = await api_update_exercise(token, exercise_uuid, {"exerciseGroupId": group_uuid})
    except httpx.RequestError as exc:
        logger.error("Ошибка смены группы у упражнения %s: %s", exercise_uuid, exc)
        await query.message.edit_text(
            _EXERCISES_INTRO + "❌ Не удалось сменить группу. Попробуйте позже.",
            parse_mode="HTML",
            reply_markup=get_exercises_menu(),
        )
        context.user_data["conversation_active"] = False
        return ConversationHandler.END

    if response.status_code not in (200, 204):
        logger.warning(
            "Ошибка API при смене группы упражнения (%s): %s",
            response.status_code,
            response.text,
        )
        await query.message.edit_text(
            _EXERCISES_INTRO + "❌ Не удалось сменить группу. Попробуйте позже.",
            parse_mode="HTML",
            reply_markup=get_exercises_menu(),
        )
        context.user_data["conversation_active"] = False
        return ConversationHandler.END

    prompt = context.user_data.get(_EXERCISE_PROMPT_KEY)
    chat_id, message_id = prompt if prompt else (query.message.chat_id, query.message.message_id)

    exercises = await _fetch_exercises(context, user_id, token) or []
    exercise = _find_exercise(exercises, exercise_uuid)

    text = _format_exercise_details(exercise or {"uuid": exercise_uuid})
    markup = get_exercise_actions_keyboard(exercise_uuid)

    if prompt:
        await _safe_edit_message(context, chat_id, message_id, text=text, reply_markup=markup)
    else:
        await query.message.edit_text(text, parse_mode="HTML", reply_markup=markup)

    _reset_exercise_flow(context)
    context.user_data["conversation_active"] = False
    return ConversationHandler.END


async def ask_delete_exercise(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Выводит подтверждение удаления упражнения."""
    query = update.callback_query
    await query.answer()
    data = query.data or ""
    parts = data.split(":", 2)
    uuid = parts[2] if len(parts) == 3 else ""

    exercises = context.user_data.get(_EXERCISE_CACHE_KEY, []) or []
    exercise = _find_exercise(exercises, uuid)
    name = html.escape(str(exercise.get("name") if exercise else "это упражнение"))

    await query.message.edit_text(
        (
            f"🗑️ Удалить упражнение <b>{name}</b>?\n"
            "Это действие необратимо и удалит упражнение из Gym-Stat."
        ),
        parse_mode="HTML",
        reply_markup=get_exercise_delete_keyboard(uuid),
    )
    context.user_data["conversation_active"] = False
    return ConversationHandler.END


async def delete_exercise(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Удаляет выбранное упражнение."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data or ""
    parts = data.split(":", 2)
    uuid = parts[2] if len(parts) == 3 else ""

    mode = await get_user_mode(user_id)
    if mode != "api":
        await query.message.edit_text(
            _EXERCISES_INTRO + "Удалять упражнения можно только в режиме Gym-Stat.",
            parse_mode="HTML",
            reply_markup=get_exercises_menu(),
        )
        context.user_data["conversation_active"] = False
        return ConversationHandler.END

    token = await get_valid_access_token(user_id)
    if not token:
        await query.message.edit_text(
            _EXERCISES_INTRO + "🔐 Авторизуйтесь через /login, чтобы управлять упражнениями.",
            parse_mode="HTML",
            reply_markup=get_exercises_menu(),
        )
        context.user_data["conversation_active"] = False
        return ConversationHandler.END

    try:
        response = await api_delete_exercise(token, uuid)
    except httpx.RequestError as exc:
        logger.error("Ошибка удаления упражнения %s: %s", uuid, exc)
        await query.message.edit_text(
            _EXERCISES_INTRO + "❌ Не удалось удалить упражнение. Попробуйте позже.",
            parse_mode="HTML",
            reply_markup=get_exercises_menu(),
        )
        context.user_data["conversation_active"] = False
        return ConversationHandler.END

    if response.status_code not in (200, 204):
        logger.warning(
            "Gym-Stat вернул ошибку при удалении упражнения (%s): %s",
            response.status_code,
            response.text,
        )
        await query.message.edit_text(
            _EXERCISES_INTRO + "❌ Не удалось удалить упражнение. Попробуйте позже.",
            parse_mode="HTML",
            reply_markup=get_exercises_menu(),
        )
        context.user_data["conversation_active"] = False
        return ConversationHandler.END

    exercises = await _fetch_exercises(context, user_id, token) or []

    await query.message.edit_text(
        (
            _EXERCISES_INTRO
            + "Упражнение успешно удалено. Вы можете создать новое или выбрать другое из списка."
        ),
        parse_mode="HTML",
        reply_markup=build_exercises_keyboard(exercises),
    )
    context.user_data["conversation_active"] = False
    return ConversationHandler.END


async def show_exercise_groups(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отображает список групп упражнений пользователя."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    requested_page = _parse_groups_page(query.data or "")

    mode = await get_user_mode(user_id)
    if mode != "api":
        await query.message.edit_text(
            (
                _DESCRIPTION_INTRO
                + "Управление группами доступно только после переключения на режим Gym-Stat."
            ),
            parse_mode="HTML",
            reply_markup=get_exercises_menu(),
        )
        context.user_data[_GROUPS_PAGE_KEY] = 1
        context.user_data["conversation_active"] = False
        return ConversationHandler.END

    token = await get_valid_access_token(user_id)
    if not token:
        await query.message.edit_text(
            (
                _DESCRIPTION_INTRO
                + "🔐 Для работы с группами выполните вход через /login или кнопку «Войти»."
            ),
            parse_mode="HTML",
            reply_markup=get_exercises_menu(),
        )
        context.user_data[_GROUPS_PAGE_KEY] = 1
        context.user_data["conversation_active"] = False
        return ConversationHandler.END

    groups = await _fetch_groups(context, user_id, token)
    if groups is None:
        await query.message.edit_text(
            (
                _DESCRIPTION_INTRO
                + "❌ Не удалось получить данные с сервера. Попробуйте повторить попытку позже."
            ),
            parse_mode="HTML",
            reply_markup=get_exercises_menu(),
        )
        context.user_data[_GROUPS_PAGE_KEY] = 1
        context.user_data["conversation_active"] = False
        return ConversationHandler.END

    page_groups, current_page, total_pages = _paginate_groups(groups, requested_page)
    context.user_data[_GROUPS_PAGE_KEY] = current_page

    await query.message.edit_text(
        _build_groups_text(page_groups, page=current_page, total_pages=total_pages),
        parse_mode="HTML",
        reply_markup=build_exercise_groups_keyboard(
            page_groups, page=current_page, total_pages=total_pages
        ),
    )
    context.user_data["conversation_active"] = False
    return ConversationHandler.END


async def show_exercise_group_details(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Показывает сведения о выбранной группе упражнений."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data or ""
    parts = data.split(":", 2)
    uuid = parts[2] if len(parts) == 3 else ""
    current_page = _get_current_groups_page(context)

    groups = context.user_data.get(_CACHE_KEY, []) or []
    group = _find_group(groups, uuid)

    if group is None:
        token = await get_valid_access_token(user_id)
        if token:
            groups = await _fetch_groups(context, user_id, token) or []
            group = _find_group(groups, uuid)

    if group is None:
        page_groups, current_page, total_pages = _paginate_groups(groups, current_page)
        context.user_data[_GROUPS_PAGE_KEY] = current_page
        await query.message.edit_text(
            (
                _DESCRIPTION_INTRO
                + "⚠️ Не удалось найти выбранную группу. Возможно, она была удалена."
            ),
            parse_mode="HTML",
            reply_markup=build_exercise_groups_keyboard(
                page_groups, page=current_page, total_pages=total_pages
            ),
        )
        context.user_data["conversation_active"] = False
        return ConversationHandler.END

    context.user_data[_UUID_KEY] = uuid
    await query.message.edit_text(
        _format_group_details(group),
        parse_mode="HTML",
        reply_markup=get_exercise_group_actions_keyboard(uuid, page=current_page),
    )
    context.user_data["conversation_active"] = False
    return ConversationHandler.END


async def prompt_create_exercise_group(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Запрашивает название новой группы упражнений."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    mode = await get_user_mode(user_id)
    if mode != "api":
        await query.message.edit_text(
            (
                _DESCRIPTION_INTRO
                + "Переключитесь на режим Gym-Stat, чтобы добавлять группы упражнений."
            ),
            parse_mode="HTML",
            reply_markup=get_exercises_menu(),
        )
        context.user_data["conversation_active"] = False
        return ConversationHandler.END

    token = await get_valid_access_token(user_id)
    if not token:
        await query.message.edit_text(
            (
                _DESCRIPTION_INTRO
                + "🔐 Авторизуйтесь через /login, чтобы создавать группы упражнений."
            ),
            parse_mode="HTML",
            reply_markup=get_exercises_menu(),
        )
        context.user_data["conversation_active"] = False
        return ConversationHandler.END

    context.user_data[_PROMPT_KEY] = (query.message.chat_id, query.message.message_id)
    context.user_data[_DRAFT_KEY] = {}

    await query.message.edit_text(
        (
            "✍️ <b>Введите название группы упражнений</b>\n"
            "Например: <code>Упражнения на грудь</code>. /cancel — отмена."
        ),
        parse_mode="HTML",
    )
    context.user_data["conversation_active"] = True
    return EXERCISE_GROUP_SET_NAME


async def handle_exercise_group_name_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает ввод названия группы (этап создания)."""
    message = update.message
    if not message or not message.text:
        return EXERCISE_GROUP_SET_NAME

    chat_id = message.chat_id
    user_message_id = message.message_id
    name = message.text.strip()
    if not name:
        warning_message = await message.reply_text(
            "⚠️ Название не может быть пустым. Укажите другое значение."
        )
        schedule_message_deletion(
            context,
            [user_message_id, warning_message.message_id],
            chat_id,
            delay=_USER_INPUT_DELETE_DELAY,
        )
        return EXERCISE_GROUP_SET_NAME

    draft = context.user_data.get(_DRAFT_KEY, {})
    draft["name"] = name
    context.user_data[_DRAFT_KEY] = draft

    prompt = context.user_data.get(_PROMPT_KEY)
    if prompt:
        chat_id, message_id = prompt
        await _safe_edit_message(
            context,
            chat_id,
            message_id,
            text=(
                "✍️ <b>Введите описание группы</b>\n"
                "Опишите, какие упражнения входят в категорию. Можно отправить «-», чтобы оставить поле пустым."
            ),
        )

    schedule_message_deletion(
        context,
        [user_message_id],
        chat_id,
        delay=_USER_INPUT_DELETE_DELAY,
    )

    context.user_data["conversation_active"] = True
    return EXERCISE_GROUP_SET_DESCRIPTION


async def handle_exercise_group_description_input(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Создаёт новую группу упражнений после ввода описания."""
    message = update.message
    if not message or message.text is None:
        return EXERCISE_GROUP_SET_DESCRIPTION

    description = message.text.strip()
    if description == "-":
        description = ""

    chat_id = message.chat_id
    user_message_id = message.message_id
    draft = context.user_data.get(_DRAFT_KEY)
    name = draft.get("name") if isinstance(draft, dict) else None
    if not name:
        error_message = await message.reply_text(
            "⚠️ Не удалось определить название группы. Попробуйте снова."
        )
        schedule_message_deletion(
            context,
            [user_message_id, error_message.message_id],
            chat_id,
            delay=_USER_INPUT_DELETE_DELAY,
        )
        _reset_flow(context)
        context.user_data["conversation_active"] = False
        return ConversationHandler.END

    user_id = message.from_user.id
    mode = await get_user_mode(user_id)
    if mode != "api":
        info_message = await message.reply_text(
            "Для создания групп необходимо включить режим Gym-Stat."
        )
        schedule_message_deletion(
            context,
            [user_message_id, info_message.message_id],
            chat_id,
            delay=_USER_INPUT_DELETE_DELAY,
        )
        _reset_flow(context)
        context.user_data["conversation_active"] = False
        return ConversationHandler.END

    token = await get_valid_access_token(user_id)
    if not token:
        info_message = await message.reply_text(
            "🔐 Пожалуйста, выполните вход через /login и повторите попытку."
        )
        schedule_message_deletion(
            context,
            [user_message_id, info_message.message_id],
            chat_id,
            delay=_USER_INPUT_DELETE_DELAY,
        )
        _reset_flow(context)
        context.user_data["conversation_active"] = False
        return ConversationHandler.END

    payload = {"name": name, "description": description}
    try:
        response = await api_create_exercise_group(token, payload)
    except httpx.RequestError as exc:
        logger.error("Ошибка создания группы для пользователя %s: %s", user_id, exc)
        error_message = await message.reply_text(
            "❌ Не удалось создать группу упражнений. Попробуйте позже."
        )
        schedule_message_deletion(
            context,
            [user_message_id, error_message.message_id],
            chat_id,
            delay=_USER_INPUT_DELETE_DELAY,
        )
        _reset_flow(context)
        context.user_data["conversation_active"] = False
        return ConversationHandler.END

    if response.status_code not in (200, 201):
        logger.warning(
            "Ошибка API при создании группы (%s): %s",
            response.status_code,
            response.text,
        )
        error_message = await message.reply_text(
            "❌ Gym-Stat вернул ошибку при создании группы. Проверьте данные и попробуйте снова."
        )
        schedule_message_deletion(
            context,
            [user_message_id, error_message.message_id],
            chat_id,
            delay=_USER_INPUT_DELETE_DELAY,
        )
        _reset_flow(context)
        context.user_data["conversation_active"] = False
        return ConversationHandler.END

    prompt = context.user_data.get(_PROMPT_KEY)
    prompt_chat_id, message_id = prompt if prompt else (message.chat_id, None)

    groups = await _fetch_groups(context, user_id, token) or []
    page_groups, current_page, total_pages = _paginate_groups(groups, 1)
    context.user_data[_GROUPS_PAGE_KEY] = current_page

    if message_id is not None:
        await _safe_edit_message(
            context,
            prompt_chat_id,
            message_id,
            text=_build_groups_text(
                page_groups, page=current_page, total_pages=total_pages
            ),
            reply_markup=build_exercise_groups_keyboard(
                page_groups, page=current_page, total_pages=total_pages
            ),
        )
    else:
        await message.reply_text(
            _build_groups_text(
                page_groups, page=current_page, total_pages=total_pages
            ),
            parse_mode="HTML",
            reply_markup=build_exercise_groups_keyboard(
                page_groups, page=current_page, total_pages=total_pages
            ),
        )

    schedule_message_deletion(
        context,
        [user_message_id],
        chat_id,
        delay=_USER_INPUT_DELETE_DELAY,
    )

    _reset_flow(context)
    context.user_data["conversation_active"] = False
    return ConversationHandler.END


async def prompt_rename_exercise_group(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Запрашивает новое название для выбранной группы."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data or ""
    parts = data.split(":", 2)
    uuid = parts[2] if len(parts) == 3 else ""

    mode = await get_user_mode(user_id)
    if mode != "api":
        await query.message.edit_text(
            _DESCRIPTION_INTRO + "Переименовать группу можно только в режиме Gym-Stat.",
            parse_mode="HTML",
            reply_markup=get_exercises_menu(),
        )
        context.user_data["conversation_active"] = False
        return ConversationHandler.END

    token = await get_valid_access_token(user_id)
    if not token:
        await query.message.edit_text(
            _DESCRIPTION_INTRO + "🔐 Авторизуйтесь в Gym-Stat, чтобы редактировать группы.",
            parse_mode="HTML",
            reply_markup=get_exercises_menu(),
        )
        context.user_data["conversation_active"] = False
        return ConversationHandler.END

    context.user_data[_UUID_KEY] = uuid
    context.user_data[_PROMPT_KEY] = (query.message.chat_id, query.message.message_id)

    await query.message.edit_text(
        (
            "✏️ <b>Введите новое название группы</b>\n"
            "Отправьте /cancel, чтобы выйти без изменений."
        ),
        parse_mode="HTML",
    )
    context.user_data["conversation_active"] = True
    return EXERCISE_GROUP_RENAME


async def handle_exercise_group_rename_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обновляет название выбранной группы упражнений."""
    message = update.message
    if not message or not message.text:
        return EXERCISE_GROUP_RENAME

    new_name = message.text.strip()
    if not new_name:
        await message.reply_text("⚠️ Название не может быть пустым. Введите другое значение.")
        return EXERCISE_GROUP_RENAME

    uuid = context.user_data.get(_UUID_KEY)
    if not uuid:
        await message.reply_text("⚠️ Не удалось определить группу. Попробуйте снова из списка групп.")
        _reset_flow(context)
        context.user_data["conversation_active"] = False
        return ConversationHandler.END

    user_id = message.from_user.id
    mode = await get_user_mode(user_id)
    if mode != "api":
        await message.reply_text("Переключите режим на Gym-Stat, чтобы редактировать группы.")
        _reset_flow(context)
        context.user_data["conversation_active"] = False
        return ConversationHandler.END

    token = await get_valid_access_token(user_id)
    if not token:
        await message.reply_text("🔐 Авторизуйтесь через /login и повторите попытку.")
        _reset_flow(context)
        context.user_data["conversation_active"] = False
        return ConversationHandler.END

    try:
        response = await api_update_exercise_group(token, uuid, {"name": new_name})
    except httpx.RequestError as exc:
        logger.error("Ошибка обновления группы %s: %s", uuid, exc)
        await message.reply_text("❌ Не удалось изменить название. Попробуйте позже.")
        _reset_flow(context)
        context.user_data["conversation_active"] = False
        return ConversationHandler.END

    if response.status_code not in (200, 204):
        logger.warning(
            "Ошибка API при переименовании группы (%s): %s",
            response.status_code,
            response.text,
        )
        await message.reply_text("❌ Gym-Stat вернул ошибку при обновлении названия группы.")
        _reset_flow(context)
        context.user_data["conversation_active"] = False
        return ConversationHandler.END

    prompt = context.user_data.get(_PROMPT_KEY)
    chat_id, message_id = prompt if prompt else (message.chat_id, None)

    groups = await _fetch_groups(context, user_id, token) or []
    group = _find_group(groups, uuid) or {"uuid": uuid, "name": new_name}
    context.user_data[_GROUPS_PAGE_KEY] = 1

    text = _format_group_details(group)
    markup = get_exercise_group_actions_keyboard(uuid, page=1)

    if message_id is not None:
        await _safe_edit_message(context, chat_id, message_id, text=text, reply_markup=markup)
    else:
        await message.reply_text(text, parse_mode="HTML", reply_markup=markup)

    _reset_flow(context)
    context.user_data["conversation_active"] = False
    return ConversationHandler.END


async def prompt_change_exercise_group_description(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Запрашивает новое описание для группы."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data or ""
    parts = data.split(":", 2)
    uuid = parts[2] if len(parts) == 3 else ""

    mode = await get_user_mode(user_id)
    if mode != "api":
        await query.message.edit_text(
            _DESCRIPTION_INTRO + "Редактирование описания доступно только в режиме Gym-Stat.",
            parse_mode="HTML",
            reply_markup=get_exercises_menu(),
        )
        context.user_data["conversation_active"] = False
        return ConversationHandler.END

    token = await get_valid_access_token(user_id)
    if not token:
        await query.message.edit_text(
            _DESCRIPTION_INTRO + "🔐 Авторизуйтесь через /login, чтобы редактировать описания групп.",
            parse_mode="HTML",
            reply_markup=get_exercises_menu(),
        )
        context.user_data["conversation_active"] = False
        return ConversationHandler.END

    context.user_data[_UUID_KEY] = uuid
    context.user_data[_PROMPT_KEY] = (query.message.chat_id, query.message.message_id)

    await query.message.edit_text(
        (
            "📝 <b>Введите новое описание группы</b>\n"
            "Если хотите оставить поле пустым, отправьте «-». /cancel — отмена."
        ),
        parse_mode="HTML",
    )
    context.user_data["conversation_active"] = True
    return EXERCISE_GROUP_UPDATE_DESCRIPTION


async def handle_exercise_group_description_update(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Обновляет описание группы упражнений."""
    message = update.message
    if not message or message.text is None:
        return EXERCISE_GROUP_UPDATE_DESCRIPTION

    description = message.text.strip()
    if description == "-":
        description = ""

    uuid = context.user_data.get(_UUID_KEY)
    if not uuid:
        await message.reply_text("⚠️ Не удалось определить группу. Откройте список и повторите попытку.")
        _reset_flow(context)
        context.user_data["conversation_active"] = False
        return ConversationHandler.END

    user_id = message.from_user.id
    mode = await get_user_mode(user_id)
    if mode != "api":
        await message.reply_text("Описание можно менять только в режиме Gym-Stat.")
        _reset_flow(context)
        context.user_data["conversation_active"] = False
        return ConversationHandler.END

    token = await get_valid_access_token(user_id)
    if not token:
        await message.reply_text("🔐 Пожалуйста, выполните вход через /login.")
        _reset_flow(context)
        context.user_data["conversation_active"] = False
        return ConversationHandler.END

    try:
        response = await api_update_exercise_group(token, uuid, {"description": description})
    except httpx.RequestError as exc:
        logger.error("Ошибка обновления описания группы %s: %s", uuid, exc)
        await message.reply_text("❌ Не удалось обновить описание. Попробуйте позже.")
        _reset_flow(context)
        context.user_data["conversation_active"] = False
        return ConversationHandler.END

    if response.status_code not in (200, 204):
        logger.warning(
            "Ошибка API при обновлении описания группы (%s): %s",
            response.status_code,
            response.text,
        )
        await message.reply_text("❌ Gym-Stat вернул ошибку при обновлении описания.")
        _reset_flow(context)
        context.user_data["conversation_active"] = False
        return ConversationHandler.END

    prompt = context.user_data.get(_PROMPT_KEY)
    chat_id, message_id = prompt if prompt else (message.chat_id, None)

    groups = await _fetch_groups(context, user_id, token) or []
    group = _find_group(groups, uuid) or {"uuid": uuid, "description": description}
    context.user_data[_GROUPS_PAGE_KEY] = 1

    text = _format_group_details(group)
    markup = get_exercise_group_actions_keyboard(uuid, page=1)

    if message_id is not None:
        await _safe_edit_message(context, chat_id, message_id, text=text, reply_markup=markup)
    else:
        await message.reply_text(text, parse_mode="HTML", reply_markup=markup)

    _reset_flow(context)
    context.user_data["conversation_active"] = False
    return ConversationHandler.END


async def ask_delete_exercise_group(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Выводит подтверждение удаления группы."""
    query = update.callback_query
    await query.answer()
    data = query.data or ""
    parts = data.split(":", 2)
    uuid = parts[2] if len(parts) == 3 else ""

    groups = context.user_data.get(_CACHE_KEY, []) or []
    group = _find_group(groups, uuid)
    name = html.escape(str(group.get("name") if group else "эту группу"))

    await query.message.edit_text(
        (
            f"🗑️ Удалить группу <b>{name}</b>?\n"
            "Это действие необратимо и удалит категорию из Gym-Stat."
        ),
        parse_mode="HTML",
        reply_markup=get_exercise_group_delete_keyboard(uuid),
    )
    context.user_data["conversation_active"] = False
    return ConversationHandler.END


async def delete_exercise_group(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Удаляет выбранную группу упражнений."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data or ""
    parts = data.split(":", 2)
    uuid = parts[2] if len(parts) == 3 else ""

    mode = await get_user_mode(user_id)
    if mode != "api":
        await query.message.edit_text(
            _DESCRIPTION_INTRO + "Удалять группы можно только в режиме Gym-Stat.",
            parse_mode="HTML",
            reply_markup=get_exercises_menu(),
        )
        context.user_data["conversation_active"] = False
        return ConversationHandler.END

    token = await get_valid_access_token(user_id)
    if not token:
        await query.message.edit_text(
            _DESCRIPTION_INTRO + "🔐 Авторизуйтесь через /login, чтобы управлять группами.",
            parse_mode="HTML",
            reply_markup=get_exercises_menu(),
        )
        context.user_data["conversation_active"] = False
        return ConversationHandler.END

    try:
        response = await api_delete_exercise_group(token, uuid)
    except httpx.RequestError as exc:
        logger.error("Ошибка удаления группы %s: %s", uuid, exc)
        await query.message.edit_text(
            _DESCRIPTION_INTRO + "❌ Не удалось удалить группу. Попробуйте позже.",
            parse_mode="HTML",
            reply_markup=get_exercises_menu(),
        )
        context.user_data["conversation_active"] = False
        return ConversationHandler.END

    if response.status_code not in (200, 204):
        logger.warning(
            "Gym-Stat вернул ошибку при удалении группы (%s): %s",
            response.status_code,
            response.text,
        )
        await query.message.edit_text(
            _DESCRIPTION_INTRO + "❌ Не удалось удалить группу. Попробуйте позже.",
            parse_mode="HTML",
            reply_markup=get_exercises_menu(),
        )
        context.user_data["conversation_active"] = False
        return ConversationHandler.END

    groups = await _fetch_groups(context, user_id, token) or []
    page_groups, current_page, total_pages = _paginate_groups(groups, 1)
    context.user_data[_GROUPS_PAGE_KEY] = current_page

    text = (
        _DESCRIPTION_INTRO
        + "Группа успешно удалена. Вы можете создать новую или выбрать другую из списка."
    )
    if groups:
        text += f"\n\nСтраница {current_page} из {total_pages}."

    await query.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=build_exercise_groups_keyboard(
            page_groups, page=current_page, total_pages=total_pages
        ),
    )
    context.user_data["conversation_active"] = False
    return ConversationHandler.END
