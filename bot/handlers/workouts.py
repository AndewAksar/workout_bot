"""Обработчики, ответственные за управление тренировками через API Gym-Stat."""

from __future__ import annotations

import html
from datetime import datetime, time, timezone
from typing import Any, Dict, Iterable, Optional
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from bot.api.gym_stat_client import (
    create_workout as api_create_workout,
    delete_workout as api_delete_workout,
    get_exercises as api_get_exercises,
    get_workout as api_get_workout,
    get_workouts as api_get_workouts,
)
from bot.config.settings import WORKOUT_CREATION
from bot.keyboards.workouts_menu import (
    build_add_set_keyboard,
    build_exercise_selection_keyboard,
    build_workouts_keyboard,
    get_workout_details_keyboard,
    get_workout_delete_keyboard,
)
from bot.utils.api_session import get_valid_access_token
from bot.utils.db_utils import get_user_mode
from bot.utils.logger import setup_logging
from bot.utils.message_deletion import schedule_message_deletion


logger = setup_logging()

_WORKOUT_STAGE_KEY = "workout_stage"
_WORKOUT_DRAFT_KEY = "workout_draft"
_WORKOUT_MESSAGE_IDS_KEY = "workout_prompt_ids"
_WORKOUT_EXERCISES_KEY = "workout_exercise_choices"
_WORKOUT_CURRENT_SET_KEY = "workout_current_set"
_WORKOUT_DETAILS_CACHE_KEY = "workout_details_cache"
_WORKOUTS_CACHE_KEY = "workouts_cache"
_WORKOUTS_PAGE_KEY = "workouts_current_page"
_WORKOUTS_PAGE_SIZE = 4
_WORKOUTS_INTRO = (
    "🗂️ <b>Ваши тренировки</b>\n"
    "Описание: Раздел помогает отслеживать и редактировать тренировки Gym-Stat.\n"
)
_DATE_FORMATS = (
    "%Y-%m-%dT%H:%M:%S.%f%z",
    "%Y-%m-%dT%H:%M:%S%z",
    "%Y-%m-%dT%H:%M:%S.%f",
    "%Y-%m-%dT%H:%M:%S",
)

_USER_INPUT_DELETE_DELAY = 15


def _parse_page_from_callback(data: Optional[str]) -> tuple[int, bool]:
    """Extracts the requested page number from callback data."""
    if not data:
        return 1, False
    if data.startswith("workouts:page:"):
        try:
            page = int(data.rsplit(":", maxsplit=1)[-1])
        except ValueError:
            return 1, False
        return (page if page > 0 else 1), True
    return 1, False


def _get_cached_workouts(context: ContextTypes.DEFAULT_TYPE) -> list[dict[str, Any]]:
    """Returns the cached workouts list from user data."""
    workouts = context.user_data.get(_WORKOUTS_CACHE_KEY)
    if isinstance(workouts, list):
        return workouts
    return []


def _set_cached_workouts(
    context: ContextTypes.DEFAULT_TYPE, workouts: Iterable[dict[str, Any]]
) -> None:
    context.user_data[_WORKOUTS_CACHE_KEY] = list(workouts)


def _get_current_page(context: ContextTypes.DEFAULT_TYPE) -> int:
    page = context.user_data.get(_WORKOUTS_PAGE_KEY)
    if isinstance(page, int) and page > 0:
        return page
    return 1


def _set_current_page(context: ContextTypes.DEFAULT_TYPE, page: int) -> None:
    context.user_data[_WORKOUTS_PAGE_KEY] = page if page > 0 else 1


def _calculate_total_pages(workouts: Iterable[dict[str, Any]]) -> int:
    items = list(workouts)
    if not items:
        return 1
    return max(1, (len(items) + _WORKOUTS_PAGE_SIZE - 1) // _WORKOUTS_PAGE_SIZE)


def _workout_sort_key(workout: dict[str, Any]) -> datetime:
    date_value = workout.get("date")
    if not isinstance(date_value, str):
        return datetime.min.replace(tzinfo=timezone.utc)
    clean = date_value.strip()
    if clean.endswith("Z"):
        clean = clean[:-1] + "+00:00"
    for fmt in _DATE_FORMATS:
        try:
            parsed = datetime.strptime(clean, fmt)
        except ValueError:
            continue
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    return datetime.min.replace(tzinfo=timezone.utc)


def _sort_workouts(workouts: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(workouts, key=_workout_sort_key, reverse=True)


def _build_workouts_text(
    workouts: Iterable[dict[str, Any]], *, page: int, total_pages: int
) -> str:
    workouts_list = list(workouts)
    if workouts_list:
        return (
            _WORKOUTS_INTRO
            + "\n"
            + f"📘 Страница {page} из {total_pages}.\n"
            + "Выберите тренировку, чтобы посмотреть детали или обновить её."
        )
    return (
        _WORKOUTS_INTRO
        + "Пока у вас нет тренировок. Нажмите «➕», чтобы добавить первую."
    )


def _build_cached_workouts_keyboard(
    context: ContextTypes.DEFAULT_TYPE, *, include_create: bool = True
):
    workouts = _get_cached_workouts(context)
    total_pages = _calculate_total_pages(workouts)
    page = min(max(_get_current_page(context), 1), total_pages)
    _set_current_page(context, page)
    return build_workouts_keyboard(
        workouts,
        page=page,
        page_size=_WORKOUTS_PAGE_SIZE,
        total_pages=total_pages,
        include_create=include_create,
    )


async def show_workouts_menu(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Displays the workouts menu with buttons to view or create workouts."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    requested_page, from_navigation = _parse_page_from_callback(query.data)

    mode = await get_user_mode(user_id)
    if mode != "api":
        keyboard = build_workouts_keyboard(
            [],
            page=1,
            page_size=_WORKOUTS_PAGE_SIZE,
            total_pages=1,
            include_create=False,
        )
        _set_cached_workouts(context, [])
        _set_current_page(context, 1)
        await query.message.edit_text(
            (
                _WORKOUTS_INTRO
                + "Тренировки доступны только в режиме Gym-Stat.\n"
                + "Переключитесь на интеграцию через кнопку ниже и выполните вход,"
                + " чтобы управлять своими тренировками и синхронизировать их с сайтом."
            ),
            parse_mode="HTML",
            reply_markup=keyboard,
        )
        context.user_data["conversation_active"] = False
        return ConversationHandler.END

    token = await get_valid_access_token(user_id)
    if not token:
        keyboard = build_workouts_keyboard(
            [],
            page=1,
            page_size=_WORKOUTS_PAGE_SIZE,
            total_pages=1,
            include_create=False,
        )
        _set_current_page(context, 1)
        await query.message.edit_text(
            (
                _WORKOUTS_INTRO
                + "🔐 <b>Нужна авторизация</b>\n"
                + "Чтобы просматривать и создавать тренировки, войдите в аккаунт Gym-Stat"
                + " через команду /login или кнопку «Войти» в меню настроек."
            ),
            parse_mode="HTML",
            reply_markup=keyboard,
        )
        context.user_data["conversation_active"] = False
        return ConversationHandler.END

    cache_exists = _WORKOUTS_CACHE_KEY in context.user_data
    workouts: list[dict[str, Any]] | None = None
    if from_navigation and cache_exists:
        workouts = _get_cached_workouts(context)

    if workouts is None or (not from_navigation):
        fetched = await _fetch_workouts(token)
        if fetched is None:
            fallback = workouts if workouts is not None else _get_cached_workouts(context)
            total_pages = _calculate_total_pages(fallback)
            page = min(max(requested_page, 1), total_pages)
            _set_current_page(context, page)
            await query.message.edit_text(
                (
                    _WORKOUTS_INTRO
                    + "❌ <b>Не удалось получить список тренировок</b>\n"
                    + "Попробуйте повторить попытку чуть позже."
                ),
                parse_mode="HTML",
                reply_markup=build_workouts_keyboard(
                    fallback,
                    page=page,
                    page_size=_WORKOUTS_PAGE_SIZE,
                    total_pages=total_pages,
                ),
            )
            context.user_data["conversation_active"] = False
            return ConversationHandler.END
        workouts = _sort_workouts(fetched)
        _set_cached_workouts(context, workouts)

    total_pages = _calculate_total_pages(workouts)
    page = min(max(requested_page, 1), total_pages)
    _set_current_page(context, page)

    description = _build_workouts_text(
        workouts, page=page, total_pages=total_pages
    )
    await query.message.edit_text(
        description,
        parse_mode="HTML",
        reply_markup=build_workouts_keyboard(
            workouts,
            page=page,
            page_size=_WORKOUTS_PAGE_SIZE,
            total_pages=total_pages,
        ),
    )
    context.user_data["conversation_active"] = False
    return ConversationHandler.END


async def show_workout_details(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Shows details for a particular workout."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    uuid = query.data.split(":", maxsplit=2)[-1]

    mode = await get_user_mode(user_id)
    if mode != "api":
        await query.message.edit_text(
            (
                "ℹ️ Просмотр тренировок доступен только при активной интеграции"
                " с Gym-Stat."
            ),
            parse_mode="HTML",
            reply_markup=_build_cached_workouts_keyboard(
                context, include_create=False
            ),
        )
        context.user_data["conversation_active"] = False
        return ConversationHandler.END

    token = await get_valid_access_token(user_id)
    if not token:
        await query.message.edit_text(
            (
                "🔐 <b>Нужна авторизация</b>\n"
                "Чтобы открыть тренировку, войдите в Gym-Stat через /login."
            ),
            parse_mode="HTML",
            reply_markup=_build_cached_workouts_keyboard(
                context, include_create=False
            ),
        )
        context.user_data["conversation_active"] = False
        return ConversationHandler.END

    workout = await _fetch_workout(token, uuid)
    if workout is None:
        await query.message.edit_text(
            (
                "❌ <b>Не удалось получить данные тренировки</b>\n"
                "Возможно, запись была удалена или временно недоступна."
            ),
            parse_mode="HTML",
            reply_markup=_build_cached_workouts_keyboard(context),
        )
        context.user_data["conversation_active"] = False
        return ConversationHandler.END

    exercise_names = await _build_exercise_name_map(token, workout)

    cache: Dict[str, Dict[str, Any]] = context.user_data.setdefault(
        _WORKOUT_DETAILS_CACHE_KEY, {}
    )
    cache[uuid] = workout

    await query.message.edit_text(
        _format_workout_details(workout, exercise_names),
        parse_mode="HTML",
        reply_markup=get_workout_details_keyboard(
            uuid, _get_current_page(context)
        ),
    )
    context.user_data["conversation_active"] = False
    return ConversationHandler.END


async def prompt_delete_workout(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Shows a confirmation prompt before deleting a workout."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    uuid = query.data.split(":", maxsplit=2)[-1]

    mode = await get_user_mode(user_id)
    if mode != "api":
        await query.message.edit_text(
            (
                "ℹ️ Просмотр тренировок доступен только при активной интеграции"
                " с Gym-Stat."
            ),
            parse_mode="HTML",
            reply_markup=_build_cached_workouts_keyboard(
                context, include_create=False
            ),
        )
        context.user_data["conversation_active"] = False
        return ConversationHandler.END

    token = await get_valid_access_token(user_id)
    if not token:
        await query.message.edit_text(
            (
                "🔐 <b>Нужна авторизация</b>\n"
                "Чтобы управлять тренировками, войдите в Gym-Stat через /login."
            ),
            parse_mode="HTML",
            reply_markup=_build_cached_workouts_keyboard(
                context, include_create=False
            ),
        )
        context.user_data["conversation_active"] = False
        return ConversationHandler.END

    cache: Dict[str, Dict[str, Any]] = context.user_data.setdefault(
        _WORKOUT_DETAILS_CACHE_KEY, {}
    )
    workout = cache.get(uuid)
    if workout is None:
        workout = await _fetch_workout(token, uuid)
        if workout is None:
            await query.message.edit_text(
                (
                    "❌ <b>Не удалось получить данные тренировки</b>\n"
                    "Попробуйте снова открыть список тренировок."
                ),
                parse_mode="HTML",
                reply_markup=_build_cached_workouts_keyboard(context),
            )
            context.user_data["conversation_active"] = False
            return ConversationHandler.END
        cache[uuid] = workout

    workout_name = html.escape(workout.get("name") or "Без названия")
    await query.message.edit_text(
        (
            "❓ <b>Удалить тренировку?</b>\n"
            f"Вы уверены, что хотите удалить «{workout_name}»?"
        ),
        parse_mode="HTML",
        reply_markup=get_workout_delete_keyboard(uuid),
    )
    context.user_data["conversation_active"] = False
    return ConversationHandler.END


async def delete_workout(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Deletes a workout after user confirmation."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    uuid = query.data.split(":", maxsplit=2)[-1]

    mode = await get_user_mode(user_id)
    if mode != "api":
        await query.message.edit_text(
            (
                "ℹ️ Удаление тренировок доступно только в режиме Gym-Stat."
            ),
            parse_mode="HTML",
            reply_markup=_build_cached_workouts_keyboard(
                context, include_create=False
            ),
        )
        context.user_data["conversation_active"] = False
        return ConversationHandler.END

    token = await get_valid_access_token(user_id)
    if not token:
        await query.message.edit_text(
            (
                "🔐 <b>Нужна авторизация</b>\n"
                "Чтобы удалять тренировки, войдите в Gym-Stat через /login."
            ),
            parse_mode="HTML",
            reply_markup=_build_cached_workouts_keyboard(
                context, include_create=False
            ),
        )
        context.user_data["conversation_active"] = False
        return ConversationHandler.END

    cache: Dict[str, Dict[str, Any]] = context.user_data.get(
        _WORKOUT_DETAILS_CACHE_KEY, {}
    )
    workout = cache.get(uuid)
    workout_name = html.escape((workout or {}).get("name") or "Без названия")

    response = await api_delete_workout(token, uuid)
    if not 200 <= response.status_code < 300:
        logger.error(
            "Не удалось удалить тренировку %s: %s", uuid, response.text
        )
        await query.message.edit_text(
            (
                "❌ <b>Не удалось удалить тренировку</b>\n"
                "Попробуйте повторить попытку чуть позже."
            ),
            parse_mode="HTML",
            reply_markup=get_workout_delete_keyboard(uuid),
        )
        context.user_data["conversation_active"] = False
        return ConversationHandler.END

    if isinstance(cache, dict):
        cache.pop(uuid, None)

    workouts = await _fetch_workouts(token)
    if workouts is None:
        cached_workouts = [
            item
            for item in _get_cached_workouts(context)
            if item.get("uuid") != uuid
        ]
        _set_cached_workouts(context, cached_workouts)
        total_pages = _calculate_total_pages(cached_workouts)
        page = min(max(_get_current_page(context), 1), total_pages)
        _set_current_page(context, page)
        await query.message.edit_text(
            (
                "✅ Тренировка удалена.\n"
                "Не удалось обновить список, попробуйте открыть меню тренировок ещё раз."
            ),
            parse_mode="HTML",
            reply_markup=build_workouts_keyboard(
                cached_workouts,
                page=page,
                page_size=_WORKOUTS_PAGE_SIZE,
                total_pages=total_pages,
            ),
        )
        context.user_data["conversation_active"] = False
        return ConversationHandler.END

    sorted_workouts = _sort_workouts(workouts)
    _set_cached_workouts(context, sorted_workouts)
    total_pages = _calculate_total_pages(sorted_workouts)
    page = min(max(_get_current_page(context), 1), total_pages)
    _set_current_page(context, page)

    await query.message.edit_text(
        (
            "🗑️ <b>Тренировка удалена</b>\n"
            f"«{workout_name}» удалена из Gym-Stat."
        ),
        parse_mode="HTML",
        reply_markup=build_workouts_keyboard(
            sorted_workouts,
            page=page,
            page_size=_WORKOUTS_PAGE_SIZE,
            total_pages=total_pages,
        ),
    )
    context.user_data["conversation_active"] = False
    return ConversationHandler.END


async def start_create_workout(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Begins the guided flow for creating a workout."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    mode = await get_user_mode(user_id)
    if mode != "api":
        await query.message.edit_text(
            (
                "🏋️ Создание тренировки доступно после переключения на режим"
                " Gym-Stat."
            ),
            parse_mode="HTML",
            reply_markup=_build_cached_workouts_keyboard(
                context, include_create=False
            ),
        )
        context.user_data["conversation_active"] = False
        return ConversationHandler.END

    token = await get_valid_access_token(user_id)
    if not token:
        await query.message.edit_text(
            (
                "🔐 <b>Сначала выполните вход</b>\n"
                "Команда /login или кнопка «Войти» в настройках помогут"
                " авторизоваться в Gym-Stat."
            ),
            parse_mode="HTML",
            reply_markup=_build_cached_workouts_keyboard(
                context, include_create=False
            ),
        )
        context.user_data["conversation_active"] = False
        return ConversationHandler.END

    context.user_data[_WORKOUT_STAGE_KEY] = "name"
    context.user_data[_WORKOUT_DRAFT_KEY] = {"sets": []}
    context.user_data[_WORKOUT_MESSAGE_IDS_KEY] = []

    chat_id = query.message.chat_id

    message = await query.message.edit_text(
        (
            "📝 <b>Введите название тренировки</b>\n"
            "Например: <code>Грудь и плечи</code>."
        ),
        parse_mode="HTML",
    )
    _remember_prompt(context, message.message_id, chat_id)
    context.user_data["conversation_active"] = True
    context.user_data["workout_token"] = token
    return WORKOUT_CREATION


async def handle_workout_creation_input(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Processes user input for each workout creation step."""
    stage = context.user_data.get(_WORKOUT_STAGE_KEY)
    draft: Dict[str, Any] = context.user_data.get(_WORKOUT_DRAFT_KEY, {})
    token: Optional[str] = context.user_data.get("workout_token")

    user_message = update.message
    if not user_message or user_message.text is None:
        return WORKOUT_CREATION

    chat_id = user_message.chat_id
    user_message_id = user_message.message_id
    text = user_message.text.strip()

    if stage is None or draft is None or token is None:
        error_message = await user_message.reply_text(
            "⚠️ Возникла ошибка. Попробуйте начать создание тренировки заново.",
        )
        schedule_message_deletion(
            context,
            [user_message_id, error_message.message_id],
            chat_id,
            delay=_USER_INPUT_DELETE_DELAY,
        )
        context.user_data["conversation_active"] = False
        _reset_workout_flow(context)
        return ConversationHandler.END

    if stage == "name":
        draft["name"] = text
        context.user_data[_WORKOUT_STAGE_KEY] = "description"
        prompt_message = await user_message.reply_text(
            (
                "📝 <b>Добавьте описание тренировки</b>\n"
                "Например: <code>Силовая работа с акцентом на базовые упражнения</code>."
            ),
            parse_mode="HTML",
        )
        _remember_prompt(context, prompt_message.message_id, chat_id)
        schedule_message_deletion(
            context,
            [user_message_id],
            chat_id,
            delay=_USER_INPUT_DELETE_DELAY,
        )
        return WORKOUT_CREATION

    if stage == "description":
        draft["description"] = text
        context.user_data[_WORKOUT_STAGE_KEY] = "date"
        prompt_message = await user_message.reply_text(
            (
                "📅 <b>Укажите дату тренировки</b> в формате"
                " <code>гггг-мм-дд</code>."
            ),
            parse_mode="HTML",
        )
        _remember_prompt(context, prompt_message.message_id, chat_id)
        schedule_message_deletion(
            context,
            [user_message_id],
            chat_id,
            delay=_USER_INPUT_DELETE_DELAY,
        )
        return WORKOUT_CREATION

    if stage == "date":
        parsed_date = _parse_user_date(text)
        if not parsed_date:
            warning_message = await user_message.reply_text(
                "⚠️ Неверный формат даты. Используйте <code>гггг-мм-дд</code>.",
                parse_mode="HTML",
            )
            _remember_prompt(context, warning_message.message_id, chat_id)
            schedule_message_deletion(
                context,
                [user_message_id, warning_message.message_id],
                chat_id,
                delay=_USER_INPUT_DELETE_DELAY,
            )
            return WORKOUT_CREATION
        draft["date"] = parsed_date
        context.user_data[_WORKOUT_STAGE_KEY] = "duration"
        prompt_message = await user_message.reply_text(
            "⏱️ <b>Укажите длительность тренировки</b> в минутах.",
            parse_mode="HTML",
        )
        _remember_prompt(context, prompt_message.message_id, chat_id)
        schedule_message_deletion(
            context,
            [user_message_id],
            chat_id,
            delay=_USER_INPUT_DELETE_DELAY,
        )
        return WORKOUT_CREATION

    if stage == "duration":
        if not text.isdigit() or int(text) <= 0:
            warning_message = await user_message.reply_text(
                "⚠️ Введите целое число минут больше нуля.",
            )
            _remember_prompt(context, warning_message.message_id, chat_id)
            schedule_message_deletion(
                context,
                [user_message_id, warning_message.message_id],
                chat_id,
                delay=_USER_INPUT_DELETE_DELAY,
            )
            return WORKOUT_CREATION
        draft["duration"] = int(text)
        context.user_data[_WORKOUT_STAGE_KEY] = "calories"
        prompt_message = await user_message.reply_text(
            "🔥 <b>Укажите потраченные калории</b> (целое число).",
            parse_mode="HTML",
        )
        _remember_prompt(context, prompt_message.message_id, chat_id)
        schedule_message_deletion(
            context,
            [user_message_id],
            chat_id,
            delay=_USER_INPUT_DELETE_DELAY,
        )
        return WORKOUT_CREATION

    if stage == "calories":
        if not text.isdigit() or int(text) < 0:
            warning_message = await user_message.reply_text(
                "⚠️ Калории вводятся целым числом не меньше нуля.",
            )
            _remember_prompt(context, warning_message.message_id, chat_id)
            schedule_message_deletion(
                context,
                [user_message_id, warning_message.message_id],
                chat_id,
                delay=_USER_INPUT_DELETE_DELAY,
            )
            return WORKOUT_CREATION
        draft["calories"] = int(text)

        exercises = await _fetch_exercises(token)
        if exercises is None:
            error_message = await user_message.reply_text(
                "❌ Не удалось получить список упражнений. Попробуйте позже.",
            )
            schedule_message_deletion(
                context,
                [user_message_id, error_message.message_id],
                chat_id,
                delay=_USER_INPUT_DELETE_DELAY,
            )
            context.user_data["conversation_active"] = False
            _reset_workout_flow(context)
            return ConversationHandler.END
        if not exercises:
            info_message = await user_message.reply_text(
                (
                    "📋 Сначала создайте хотя бы одно упражнение в разделе"
                    " «Упражнения», затем повторите создание тренировки."
                )
            )
            schedule_message_deletion(
                context,
                [user_message_id, info_message.message_id],
                chat_id,
                delay=_USER_INPUT_DELETE_DELAY,
            )
            context.user_data["conversation_active"] = False
            _reset_workout_flow(context)
            return ConversationHandler.END

        draft.setdefault("sets", [])
        context.user_data[_WORKOUT_STAGE_KEY] = "add_set_prompt"
        context.user_data[_WORKOUT_EXERCISES_KEY] = {
            exercise.get("uuid"): exercise for exercise in exercises if exercise.get("uuid")
        }
        context.user_data.pop(_WORKOUT_CURRENT_SET_KEY, None)
        keyboard = build_add_set_keyboard()
        prompt_message = await user_message.reply_text(
            (
                "💪 <b>Создать подход?</b>."
                " После выбора бот попросит указать вес, количество повторов и интенсивность."
            ),
            parse_mode="HTML",
            reply_markup=keyboard,
        )
        _remember_prompt(context, prompt_message.message_id, chat_id)
        schedule_message_deletion(
            context,
            [user_message_id],
            chat_id,
            delay=_USER_INPUT_DELETE_DELAY,
        )
        return WORKOUT_CREATION

    if stage == "add_set_prompt":
        info_message = await user_message.reply_text(
            "ℹ️ Используйте кнопки «Да» или «Нет», чтобы добавить подход или завершить создание.",
        )
        _remember_prompt(context, info_message.message_id, chat_id)
        schedule_message_deletion(
            context,
            [user_message_id, info_message.message_id],
            chat_id,
            delay=_USER_INPUT_DELETE_DELAY,
        )
        return WORKOUT_CREATION

    if stage == "exercise":
        info_message = await user_message.reply_text(
            "ℹ️ Выберите упражнение, используя кнопки под предыдущим сообщением.",
        )
        _remember_prompt(context, info_message.message_id, chat_id)
        schedule_message_deletion(
            context,
            [user_message_id, info_message.message_id],
            chat_id,
            delay=_USER_INPUT_DELETE_DELAY,
        )
        return WORKOUT_CREATION

    if stage == "weight":
        current_set = context.user_data.get(_WORKOUT_CURRENT_SET_KEY)
        if not current_set or not current_set.get("exerciseId"):
            context.user_data[_WORKOUT_STAGE_KEY] = "exercise"
            warning_message = await user_message.reply_text(
                "⚠️ Сначала выберите упражнение с помощью кнопок.",
            )
            _remember_prompt(context, warning_message.message_id, chat_id)
            schedule_message_deletion(
                context,
                [user_message_id, warning_message.message_id],
                chat_id,
                delay=_USER_INPUT_DELETE_DELAY,
            )
            return WORKOUT_CREATION

        weight = _parse_number(text)
        if weight is None or weight <= 0:
            warning_message = await user_message.reply_text(
                "⚠️ Вес указывается положительным числом. Пример: 60 или 60.5",
            )
            _remember_prompt(context, warning_message.message_id, chat_id)
            schedule_message_deletion(
                context,
                [user_message_id, warning_message.message_id],
                chat_id,
                delay=_USER_INPUT_DELETE_DELAY,
            )
            return WORKOUT_CREATION

        counts = current_set.setdefault("counts", {})
        counts["weight"] = weight
        context.user_data[_WORKOUT_STAGE_KEY] = "reps"
        prompt_message = await user_message.reply_text(
            "🔢 Укажите количество повторов для подхода (целое число).",
        )
        _remember_prompt(context, prompt_message.message_id, chat_id)
        schedule_message_deletion(
            context,
            [user_message_id],
            chat_id,
            delay=_USER_INPUT_DELETE_DELAY,
        )
        return WORKOUT_CREATION

    if stage == "reps":
        current_set = context.user_data.get(_WORKOUT_CURRENT_SET_KEY)
        if not current_set or not current_set.get("exerciseId"):
            context.user_data[_WORKOUT_STAGE_KEY] = "exercise"
            warning_message = await user_message.reply_text(
                "⚠️ Сначала выберите упражнение с помощью кнопок.",
            )
            _remember_prompt(context, warning_message.message_id, chat_id)
            schedule_message_deletion(
                context,
                [user_message_id, warning_message.message_id],
                chat_id,
                delay=_USER_INPUT_DELETE_DELAY,
            )
            return WORKOUT_CREATION

        counts = current_set.setdefault("counts", {})
        if counts.get("weight") is None:
            context.user_data[_WORKOUT_STAGE_KEY] = "weight"
            warning_message = await user_message.reply_text(
                "⚠️ Сначала укажите вес для подхода.",
            )
            _remember_prompt(context, warning_message.message_id, chat_id)
            schedule_message_deletion(
                context,
                [user_message_id, warning_message.message_id],
                chat_id,
                delay=_USER_INPUT_DELETE_DELAY,
            )
            return WORKOUT_CREATION

        if not text.isdigit() or int(text) <= 0:
            warning_message = await user_message.reply_text(
                "⚠️ Повторы вводятся целым числом больше нуля.",
            )
            _remember_prompt(context, warning_message.message_id, chat_id)
            schedule_message_deletion(
                context,
                [user_message_id, warning_message.message_id],
                chat_id,
                delay=_USER_INPUT_DELETE_DELAY,
            )
            return WORKOUT_CREATION

        counts["reps"] = int(text)
        context.user_data[_WORKOUT_STAGE_KEY] = "intensity"
        prompt_message = await user_message.reply_text(
            (
                "💥 Укажите степень интенсивности (например: <code>no-failure</code>,"
                " <code>muscle-failure</code>, <code>technical-failure</code>)."
                " Чтобы пропустить, отправьте <code>-</code>."
            ),
            parse_mode="HTML",
        )
        _remember_prompt(context, prompt_message.message_id, chat_id)
        schedule_message_deletion(
            context,
            [user_message_id],
            chat_id,
            delay=_USER_INPUT_DELETE_DELAY,
        )
        return WORKOUT_CREATION

    if stage == "intensity":
        current_set = context.user_data.get(_WORKOUT_CURRENT_SET_KEY)
        if not current_set or not current_set.get("exerciseId"):
            context.user_data[_WORKOUT_STAGE_KEY] = "exercise"
            warning_message = await user_message.reply_text(
                "⚠️ Сначала выберите упражнение с помощью кнопок.",
            )
            _remember_prompt(context, warning_message.message_id, chat_id)
            schedule_message_deletion(
                context,
                [user_message_id, warning_message.message_id],
                chat_id,
                delay=_USER_INPUT_DELETE_DELAY,
            )
            return WORKOUT_CREATION

        counts = current_set.setdefault("counts", {})
        if counts.get("weight") is None:
            context.user_data[_WORKOUT_STAGE_KEY] = "weight"
            warning_message = await user_message.reply_text(
                "⚠️ Сначала укажите вес для подхода.",
            )
            _remember_prompt(context, warning_message.message_id, chat_id)
            schedule_message_deletion(
                context,
                [user_message_id, warning_message.message_id],
                chat_id,
                delay=_USER_INPUT_DELETE_DELAY,
            )
            return WORKOUT_CREATION
        if counts.get("reps") is None:
            context.user_data[_WORKOUT_STAGE_KEY] = "reps"
            warning_message = await user_message.reply_text(
                "⚠️ Сначала введите количество повторов.",
            )
            _remember_prompt(context, warning_message.message_id, chat_id)
            schedule_message_deletion(
                context,
                [user_message_id, warning_message.message_id],
                chat_id,
                delay=_USER_INPUT_DELETE_DELAY,
            )
            return WORKOUT_CREATION

        intensity_value = text.strip()
        if intensity_value and intensity_value != "-":
            counts["type"] = intensity_value.replace(" ", "-").lower()
        else:
            counts.pop("type", None)

        weight_value = counts.get("weight")
        if isinstance(weight_value, float) and weight_value.is_integer():
            counts["weight"] = int(weight_value)

        set_entry = {
            "exerciseId": current_set.get("exerciseId"),
            "counts": {
                "reps": counts.get("reps"),
                "weight": counts.get("weight"),
            },
        }
        if counts.get("type"):
            set_entry["counts"]["type"] = counts["type"]

        draft.setdefault("sets", []).append(set_entry)
        context.user_data.pop(_WORKOUT_CURRENT_SET_KEY, None)
        context.user_data[_WORKOUT_STAGE_KEY] = "add_set_prompt"
        keyboard = build_add_set_keyboard()
        prompt_message = await user_message.reply_text(
            "✅ Подход добавлен. Хотите создать ещё один?",
            reply_markup=keyboard,
        )
        _remember_prompt(context, prompt_message.message_id, chat_id)
        schedule_message_deletion(
            context,
            [user_message_id],
            chat_id,
            delay=_USER_INPUT_DELETE_DELAY,
        )
        return WORKOUT_CREATION

    warning_message = await user_message.reply_text(
        "⚠️ Неизвестный шаг. Попробуйте начать заново.",
    )
    schedule_message_deletion(
        context,
        [user_message_id, warning_message.message_id],
        chat_id,
        delay=_USER_INPUT_DELETE_DELAY,
    )
    context.user_data["conversation_active"] = False
    _reset_workout_flow(context)
    return ConversationHandler.END


async def handle_workout_exercise_selection(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Handles exercise selection within the workout creation flow."""
    query = update.callback_query
    await query.answer()
    exercise_uuid = query.data.split(":", maxsplit=2)[-1]

    stage = context.user_data.get(_WORKOUT_STAGE_KEY)
    if stage != "exercise":
        await query.message.edit_text(
            "⚠️ Сейчас выбор упражнения недоступен. Начните создание тренировки заново.",
        )
        context.user_data["conversation_active"] = False
        _reset_workout_flow(context)
        return ConversationHandler.END

    draft: Dict[str, Any] = context.user_data.get(_WORKOUT_DRAFT_KEY, {})
    exercise_choices: Dict[str, Dict[str, Any]] = context.user_data.get(
        _WORKOUT_EXERCISES_KEY, {}
    )
    if exercise_uuid not in exercise_choices:
        await query.message.edit_text(
            "⚠️ Выбранное упражнение недоступно. Попробуйте выбрать другое.",
            reply_markup=build_exercise_selection_keyboard(
                exercise_choices.values(),
                page=_get_current_page(context),
            ),
        )
        return WORKOUT_CREATION

    draft.setdefault("sets", [])
    context.user_data[_WORKOUT_CURRENT_SET_KEY] = {
        "exerciseId": exercise_uuid,
        "counts": {},
    }
    context.user_data[_WORKOUT_STAGE_KEY] = "weight"
    chat_id = query.message.chat_id
    prompt_message = await query.message.edit_text(
        (
            "⚖️ Введите вес для подхода. Можно указать дробное значение через"
            " точку."
        )
    )
    _remember_prompt(context, prompt_message.message_id, chat_id)

    return WORKOUT_CREATION


async def handle_workout_add_set_choice(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Handles confirmation whether to add another workout set or finish."""
    query = update.callback_query
    await query.answer()
    choice = query.data.split(":", maxsplit=3)[-1]

    stage = context.user_data.get(_WORKOUT_STAGE_KEY)
    if stage != "add_set_prompt":
        await query.message.edit_text(
            "⚠️ Сейчас нельзя изменить количество подходов. Начните создание заново.",
        )
        context.user_data["conversation_active"] = False
        _reset_workout_flow(context)
        return ConversationHandler.END

    draft: Dict[str, Any] = context.user_data.get(_WORKOUT_DRAFT_KEY, {})
    token: Optional[str] = context.user_data.get("workout_token")

    if choice == "yes":
        exercise_choices: Dict[str, Dict[str, Any]] = context.user_data.get(
            _WORKOUT_EXERCISES_KEY, {}
        )
        if not exercise_choices:
            await query.message.edit_text(
                "⚠️ Нет доступных упражнений. Создайте их в соответствующем разделе.",
            )
            context.user_data["conversation_active"] = False
            _reset_workout_flow(context)
            return ConversationHandler.END

        context.user_data[_WORKOUT_STAGE_KEY] = "exercise"
        context.user_data[_WORKOUT_CURRENT_SET_KEY] = {"counts": {}}
        keyboard = build_exercise_selection_keyboard(
            exercise_choices.values(),
            page=_get_current_page(context),
        )
        chat_id = query.message.chat_id

        prompt_message = await query.message.edit_text(
            (
                "💪 <b>Выберите упражнение для подхода</b>."
                " После выбора бот попросит указать вес, повторы и интенсивность."
            ),
            parse_mode="HTML",
            reply_markup=keyboard,
        )
        _remember_prompt(context, prompt_message.message_id, chat_id)
        return WORKOUT_CREATION

    if choice == "no":
        sets = draft.get("sets") or []
        if not sets:
            await query.message.edit_text(
                "⚠️ Тренировка должна содержать хотя бы один подход.",
                reply_markup=build_add_set_keyboard(),
            )
            return WORKOUT_CREATION

        if token is None:
            await query.message.edit_text(
                "⚠️ Не удалось подготовить данные тренировки. Попробуйте снова.",
            )
            context.user_data["conversation_active"] = False
            _reset_workout_flow(context)
            return ConversationHandler.END

        payload = _prepare_payload(draft)
        if payload is None:
            await query.message.edit_text(
                "⚠️ Не удалось подготовить данные тренировки. Попробуйте снова.",
            )
            context.user_data["conversation_active"] = False
            _reset_workout_flow(context)
            return ConversationHandler.END

        response = await api_create_workout(token, payload)
        if response.status_code not in (200, 201):
            logger.warning(
                "Ошибка создания тренировки: %s", response.text
            )
            await query.message.edit_text(
                "❌ Не удалось создать тренировку. Попробуйте повторить попытку позже.",
            )
            context.user_data["conversation_active"] = False
            _reset_workout_flow(context)
            return ConversationHandler.END

        workouts = await _fetch_workouts(token)
        success_message = "✅ <b>Тренировка успешно сохранена в Gym-Stat!</b>"

        if workouts is None:
            cached_workouts = _get_cached_workouts(context)
            total_pages = _calculate_total_pages(cached_workouts)
            page = min(max(_get_current_page(context), 1), total_pages)
            _set_current_page(context, page)
            await query.message.edit_text(
                success_message
                + "\nНе удалось обновить список, попробуйте открыть меню тренировок ещё раз.",
                parse_mode="HTML",
                reply_markup=build_workouts_keyboard(
                    cached_workouts,
                    page=page,
                    page_size=_WORKOUTS_PAGE_SIZE,
                    total_pages=total_pages,
                ),
            )
            context.user_data["conversation_active"] = False
            _reset_workout_flow(context)
            return ConversationHandler.END

        sorted_workouts = _sort_workouts(workouts)
        _set_cached_workouts(context, sorted_workouts)
        total_pages = _calculate_total_pages(sorted_workouts)
        page = min(max(_get_current_page(context), 1), total_pages)
        _set_current_page(context, page)

        await query.message.edit_text(
            success_message,
            parse_mode="HTML",
            reply_markup=build_workouts_keyboard(
                sorted_workouts,
                page=page,
                page_size=_WORKOUTS_PAGE_SIZE,
                total_pages=total_pages,
            ),
        )
        context.user_data["conversation_active"] = False
        _reset_workout_flow(context)
        return ConversationHandler.END

    await query.message.edit_text(
        "⚠️ Неизвестный вариант выбора. Попробуйте снова.",
        reply_markup=build_add_set_keyboard(),
    )
    return WORKOUT_CREATION


async def _fetch_workouts(token: str) -> Optional[list[dict[str, Any]]]:
    response = await api_get_workouts(token)
    if response.status_code != 200:
        logger.warning("Не удалось получить тренировки: %s", response.text)
        return None
    try:
        data = response.json()
    except ValueError:
        logger.error("Некорректный JSON списка тренировок")
        return None
    if isinstance(data, list):
        return data
    logger.error("Неожиданный формат списка тренировок: %s", data)
    return None


async def _fetch_workout(token: str, uuid: str) -> Optional[dict[str, Any]]:
    response = await api_get_workout(token, uuid)
    if response.status_code != 200:
        logger.warning("Не удалось получить тренировку %s: %s", uuid, response.text)
        return None
    try:
        data = response.json()
    except ValueError:
        logger.error("Некорректный JSON тренировки %s", uuid)
        return None
    if isinstance(data, dict):
        return data
    logger.error("Неожиданный формат данных тренировки %s: %s", uuid, data)
    return None


async def _fetch_exercises(token: str) -> Optional[list[dict[str, Any]]]:
    response = await api_get_exercises(token)
    if response.status_code != 200:
        logger.warning("Не удалось получить упражнения: %s", response.text)
        return None
    try:
        data = response.json()
    except ValueError:
        logger.error("Некорректный JSON упражнений")
        return None
    if isinstance(data, list):
        return data
    logger.error("Неожиданный формат списка упражнений: %s", data)
    return None


async def _build_exercise_name_map(
    token: str,
    workout: dict[str, Any],
) -> dict[str, str]:
    """Возвращает словарь названий упражнений, используемых в тренировке."""

    sets = workout.get("sets") or []
    if not sets:
        return {}

    # Если API уже вернул вложенные данные упражнения, повторный запрос не нужен.
    needs_lookup = False
    for workout_set in sets:
        if not isinstance(workout_set, dict):
            continue
        exercise = workout_set.get("exercise")
        if isinstance(exercise, dict) and exercise.get("name"):
            continue
        exercise_id = workout_set.get("exerciseId") or workout_set.get("exercise_id")
        if exercise_id:
            needs_lookup = True
            break

    if not needs_lookup:
        return {}

    exercises = await _fetch_exercises(token)
    if not exercises:
        return {}

    result: dict[str, str] = {}
    for exercise in exercises:
        if not isinstance(exercise, dict):
            continue
        exercise_uuid = exercise.get("uuid")
        if not exercise_uuid:
            continue
        result[str(exercise_uuid)] = str(exercise.get("name") or "Без названия")

    return result

def _format_workout_details(
    workout: dict[str, Any],
    exercise_names: dict[str, str] | None = None,
) -> str:
    exercise_names = exercise_names or {}
    name = workout.get("name") or "Без названия"
    description = workout.get("description") or "—"
    date_value = workout.get("date")
    duration = workout.get("duration")
    calories = workout.get("calories")

    parts = [
        f"🏋️ <b>{name}</b>",
        f"Описание: {description}",
    ]
    if date_value:
        parts.append(f"Дата: {_format_date(date_value)}")
    if duration:
        parts.append(f"Длительность: {duration} мин")
    if calories is not None:
        parts.append(f"Калории: {calories}")

    sets = workout.get("sets") or []
    if sets:
        parts.append("\n<b>Подходы:</b> 💪")
        for idx, workout_set in enumerate(sets, start=1):
            exercise_label = _format_exercise_label(workout_set, exercise_names)
            counts = workout_set.get("counts") or []
            parts.append(f"\n{idx}. <i>Упражнение:</i> {exercise_label}️")
            for count_idx, count in enumerate(counts, start=1):
                reps = count.get("reps")
                weight = count.get("weight")
                intensity = count.get("type")
                line = f"   • Подход {count_idx}: {reps} повторов, вес {weight} кг"
                if intensity:
                    line += f", интенсивность: {intensity}"
                parts.append(line)
    else:
        parts.append("\nПодходы ещё не добавлены.")

    return "\n".join(parts)


def _format_exercise_label(
    workout_set: dict[str, Any],
    exercise_names: dict[str, str],
) -> str:
    exercise = workout_set.get("exercise")
    if isinstance(exercise, dict):
        exercise_name = exercise.get("name")
        if exercise_name:
            return html.escape(str(exercise_name))

    exercise_id = workout_set.get("exerciseId") or workout_set.get("exercise_id")
    if exercise_id is None:
        return "—"

    exercise_id_str = str(exercise_id)
    mapped_name = exercise_names.get(exercise_id_str)
    if mapped_name:
        return html.escape(mapped_name)

    return html.escape(exercise_id_str)


def _parse_user_date(value: str) -> Optional[str]:
    ### ИЗМЕНЕНО: Добавлено принудительное включение .000 и Z для полного ISO-8601
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return None
    current_time = datetime.now().time().replace(microsecond=0)  # Сбрасываем микросекунды для .000
    result = datetime.combine(parsed.date(), current_time)
    result = result.replace(tzinfo=timezone.utc)
    iso = result.isoformat()
    if '.' not in iso:
        iso = iso[:-6] + '.000' + iso[-6:]
    return iso.replace('+00:00', 'Z')  # Возвращает 'YYYY-MM-DDTHH:MM:SS.000Z'


def _parse_number(value: str) -> Optional[float]:
    normalized = value.replace(",", ".")
    try:
        return float(normalized)
    except ValueError:
        return None


def _format_date(value: str) -> str:
    clean = value.strip()
    if clean.endswith("Z"):
        clean = clean[:-1] + "+00:00"
    for fmt in _DATE_FORMATS:
        try:
            parsed = datetime.strptime(clean, fmt)
        except ValueError:
            continue
        return parsed.strftime("%d.%m.%Y")
    return value


def _prepare_payload(draft: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    name = draft.get("name")
    description = draft.get("description")
    date_value = draft.get("date")
    duration = draft.get("duration")
    calories = draft.get("calories")
    sets: Iterable[Dict[str, Any]] = draft.get("sets") or []

    if not all([name, description, date_value, duration is not None, calories is not None]):
        return None
    if not sets:
        return None

    prepared_sets: list[Dict[str, Any]] = []
    for workout_set in sets:
        exercise_id = workout_set.get("exerciseId")
        counts: Dict[str, Any] = workout_set.get("counts", {})
        reps = counts.get("reps")
        weight = counts.get("weight")
        if not exercise_id or reps is None or weight is None:
            return None

        if isinstance(weight, float) and weight.is_integer():
            weight = int(weight)

        count_entry: Dict[str, Any] = {
            "reps": reps,
            "weight": weight,
        }
        if counts.get("type"):
            count_entry["type"] = counts["type"]

        prepared_sets.append(
            {
                "exerciseId": exercise_id,
                "counts": [count_entry],
            }
        )

    payload = {
        "name": name,
        "description": description,
        "date": date_value,
        "duration": duration,
        "calories": calories,
        "sets": prepared_sets,
    }
    return payload


def _reset_workout_flow(context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.pop(_WORKOUT_STAGE_KEY, None)
    context.user_data.pop(_WORKOUT_DRAFT_KEY, None)
    context.user_data.pop(_WORKOUT_MESSAGE_IDS_KEY, None)
    context.user_data.pop(_WORKOUT_EXERCISES_KEY, None)
    context.user_data.pop(_WORKOUT_CURRENT_SET_KEY, None)
    context.user_data.pop("workout_token", None)


def _remember_prompt(
    context: ContextTypes.DEFAULT_TYPE,
    message_id: int,
    chat_id: int,
    *,
    delay: Optional[int] = None,
) -> None:
    actual_delay = _USER_INPUT_DELETE_DELAY if delay is None else delay
    context.user_data.setdefault(_WORKOUT_MESSAGE_IDS_KEY, []).append(message_id)
    schedule_message_deletion(context, [message_id], chat_id, delay=actual_delay)