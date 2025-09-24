"""Обработчики раздела "Мои упражнения" и управление группами упражнений."""

from __future__ import annotations

import html
from datetime import datetime, timezone
from typing import Any, Iterable, Optional

import httpx
from telegram import Update
from telegram.error import TelegramError
from telegram.ext import ContextTypes, ConversationHandler

from bot.api.gym_stat_client import (
    create_exercise_group as api_create_exercise_group,
    delete_exercise_group as api_delete_exercise_group,
    get_exercise_groups as api_get_exercise_groups,
    update_exercise_group as api_update_exercise_group,
)
from bot.config.settings import (
    EXERCISE_GROUP_RENAME,
    EXERCISE_GROUP_SET_DESCRIPTION,
    EXERCISE_GROUP_SET_NAME,
    EXERCISE_GROUP_UPDATE_DESCRIPTION,
)
from bot.keyboards.exercises_menu import (
    build_exercise_groups_keyboard,
    get_exercise_group_actions_keyboard,
    get_exercise_group_delete_keyboard,
    get_exercises_menu,
)
from bot.utils.api_session import get_valid_access_token
from bot.utils.db_utils import get_user_mode
from bot.utils.logger import setup_logging


logger = setup_logging()

_PROMPT_KEY = "exercise_group_prompt"
_DRAFT_KEY = "exercise_group_draft"
_UUID_KEY = "exercise_group_uuid"
_CACHE_KEY = "exercise_groups_cache"


_DESCRIPTION_INTRO = (
    "🗂️ <b>Группы упражнений</b>\n"
    "Описание: Группы помогают объединять упражнения по категориям и быстрее находить их в тренировках.\n"
)


async def show_exercises_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Показывает раздел «Мои упражнения» с выбором дальнейших действий."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    mode = await get_user_mode(user_id)

    if mode == "api":
        details = (
            "Здесь вы можете управлять группами упражнений Gym-Stat и в дальнейшем добавлять сами упражнения.\n"
            "Выберите нужный раздел ниже."
        )
    else:
        details = (
            "Сейчас активен локальный режим. Для работы с упражнениями и группами подключите режим Gym-Stat через «🔄 Сменить режим».\n"
            "После авторизации появится возможность создавать категории упражнений."
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


async def show_exercises_placeholder(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Заглушка для раздела «Упражнения» (будет реализован позже)."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    mode = await get_user_mode(user_id)

    if mode == "api":
        message = (
            "📋 Раздел «Упражнения» находится в разработке.\n"
            "Вы уже можете создавать группы упражнений, чтобы позже добавлять в них упражнения из Gym-Stat."
        )
    else:
        message = (
            "📋 Раздел «Упражнения» появится позже.\n"
            "Подключите режим Gym-Stat, чтобы управлять категориями упражнений и синхронизировать данные."
        )

    await query.message.edit_text(
        f"{message}\n\nВыберите действие ниже:",
        parse_mode="HTML",
        reply_markup=get_exercises_menu(),
    )
    context.user_data["conversation_active"] = False
    return ConversationHandler.END


def _reset_flow(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Удаляет временные данные, связанные с управлением группами упражнений."""
    for key in (_PROMPT_KEY, _DRAFT_KEY, _UUID_KEY):
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
    return dt.strftime("%d.%m.%Y %H:%M")


def _format_group_details(group: dict) -> str:
    name = html.escape(str(group.get("name") or "Без названия"))
    description_raw = str(group.get("description") or "—")
    description = html.escape(description_raw)
    uuid = html.escape(str(group.get("uuid") or "—"))
    created = _format_datetime(group.get("createdAt") or group.get("created_at"))
    updated = _format_datetime(group.get("updatedAt") or group.get("updated_at"))

    lines = [
        f"🗂️ <b>{name}</b>",
        f"Описание: {description}",
        f"UUID: <code>{uuid}</code>",
    ]
    if created:
        lines.append(f"Создано: {created}")
    if updated:
        lines.append(f"Обновлено: {updated}")
    lines.append(
        "\nИспользуйте кнопки ниже, чтобы переименовать группу, обновить описание или удалить её."
    )
    return "\n".join(lines)


def _build_groups_text(groups: Iterable[dict]) -> str:
    groups_list = list(groups)
    if groups_list:
        return (
            _DESCRIPTION_INTRO
            + "Выберите группу, чтобы посмотреть детали или изменить её параметры."
        )
    return (
        _DESCRIPTION_INTRO
        + "Пока у вас нет групп упражнений. Нажмите «➕ Создать группу», чтобы добавить первую."
    )


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

    groups = _filter_groups(response.json() or [])
    context.user_data[_CACHE_KEY] = groups
    return groups


async def show_exercise_groups(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отображает список групп упражнений пользователя."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

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
        context.user_data["conversation_active"] = False
        return ConversationHandler.END

    await query.message.edit_text(
        _build_groups_text(groups),
        parse_mode="HTML",
        reply_markup=build_exercise_groups_keyboard(groups),
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

    groups = context.user_data.get(_CACHE_KEY, []) or []
    group = _find_group(groups, uuid)

    if group is None:
        token = await get_valid_access_token(user_id)
        if token:
            groups = await _fetch_groups(context, user_id, token) or []
            group = _find_group(groups, uuid)

    if group is None:
        await query.message.edit_text(
            (
                _DESCRIPTION_INTRO
                + "⚠️ Не удалось найти выбранную группу. Возможно, она была удалена."
            ),
            parse_mode="HTML",
            reply_markup=build_exercise_groups_keyboard(groups),
        )
        context.user_data["conversation_active"] = False
        return ConversationHandler.END

    context.user_data[_UUID_KEY] = uuid
    await query.message.edit_text(
        _format_group_details(group),
        parse_mode="HTML",
        reply_markup=get_exercise_group_actions_keyboard(uuid),
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

    name = message.text.strip()
    if not name:
        await message.reply_text("⚠️ Название не может быть пустым. Укажите другое значение.")
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

    draft = context.user_data.get(_DRAFT_KEY)
    name = draft.get("name") if isinstance(draft, dict) else None
    if not name:
        await message.reply_text("⚠️ Не удалось определить название группы. Попробуйте снова.")
        _reset_flow(context)
        context.user_data["conversation_active"] = False
        return ConversationHandler.END

    user_id = message.from_user.id
    mode = await get_user_mode(user_id)
    if mode != "api":
        await message.reply_text("Для создания групп необходимо включить режим Gym-Stat.")
        _reset_flow(context)
        context.user_data["conversation_active"] = False
        return ConversationHandler.END

    token = await get_valid_access_token(user_id)
    if not token:
        await message.reply_text("🔐 Пожалуйста, выполните вход через /login и повторите попытку.")
        _reset_flow(context)
        context.user_data["conversation_active"] = False
        return ConversationHandler.END

    payload = {"name": name, "description": description}
    try:
        response = await api_create_exercise_group(token, payload)
    except httpx.RequestError as exc:
        logger.error("Ошибка создания группы для пользователя %s: %s", user_id, exc)
        await message.reply_text("❌ Не удалось создать группу упражнений. Попробуйте позже.")
        _reset_flow(context)
        context.user_data["conversation_active"] = False
        return ConversationHandler.END

    if response.status_code not in (200, 201):
        logger.warning(
            "Ошибка API при создании группы (%s): %s",
            response.status_code,
            response.text,
        )
        await message.reply_text("❌ Gym-Stat вернул ошибку при создании группы. Проверьте данные и попробуйте снова.")
        _reset_flow(context)
        context.user_data["conversation_active"] = False
        return ConversationHandler.END

    prompt = context.user_data.get(_PROMPT_KEY)
    chat_id, message_id = prompt if prompt else (message.chat_id, None)

    groups = await _fetch_groups(context, user_id, token) or []

    if message_id is not None:
        await _safe_edit_message(
            context,
            chat_id,
            message_id,
            text=_build_groups_text(groups),
            reply_markup=build_exercise_groups_keyboard(groups),
        )
    else:
        await message.reply_text(
            _build_groups_text(groups),
            parse_mode="HTML",
            reply_markup=build_exercise_groups_keyboard(groups),
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

    text = _format_group_details(group)
    markup = get_exercise_group_actions_keyboard(uuid)

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

    text = _format_group_details(group)
    markup = get_exercise_group_actions_keyboard(uuid)

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

    await query.message.edit_text(
        (
            _DESCRIPTION_INTRO
            + "Группа успешно удалена. Вы можете создать новую или выбрать другую из списка."
        ),
        parse_mode="HTML",
        reply_markup=build_exercise_groups_keyboard(groups),
    )
    context.user_data["conversation_active"] = False
    return ConversationHandler.END
