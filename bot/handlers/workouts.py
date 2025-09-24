"""Handlers responsible for managing workouts via Gym-Stat API."""
from __future__ import annotations

from datetime import datetime, time
from typing import Any, Dict, Iterable, Optional

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from bot.api.gym_stat_client import (
    create_workout as api_create_workout,
    get_exercises as api_get_exercises,
    get_workout as api_get_workout,
    get_workouts as api_get_workouts,
)
from bot.config.settings import WORKOUT_CREATION
from bot.keyboards.workouts_menu import (
    build_exercise_selection_keyboard,
    build_workouts_keyboard,
    get_workout_details_keyboard,
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
_DATE_FORMATS = (
    "%Y-%m-%dT%H:%M:%S.%f%z",
    "%Y-%m-%dT%H:%M:%S%z",
    "%Y-%m-%dT%H:%M:%S.%f",
    "%Y-%m-%dT%H:%M:%S",
)


async def show_workouts_menu(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Displays the workouts menu with buttons to view or create workouts."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    mode = await get_user_mode(user_id)
    if mode != "api":
        await query.message.edit_text(
            (
                "🏋️ <b>Тренировки доступны только в режиме Gym-Stat</b>\n"
                "Переключитесь на интеграцию через кнопку ниже и выполните вход,"
                " чтобы управлять своими тренировками и синхронизировать их с сайтом."
            ),
            parse_mode="HTML",
            reply_markup=build_workouts_keyboard([], include_create=False),
        )
        context.user_data["conversation_active"] = False
        return ConversationHandler.END

    token = await get_valid_access_token(user_id)
    if not token:
        await query.message.edit_text(
            (
                "🔐 <b>Нужна авторизация</b>\n"
                "Чтобы просматривать и создавать тренировки, войдите в аккаунт Gym-Stat"
                " через команду /login или кнопку «Войти» в меню настроек."
            ),
            parse_mode="HTML",
            reply_markup=build_workouts_keyboard([], include_create=False),
        )
        context.user_data["conversation_active"] = False
        return ConversationHandler.END

    workouts = await _fetch_workouts(token)
    if workouts is None:
        await query.message.edit_text(
            (
                "❌ <b>Не удалось получить список тренировок</b>\n"
                "Попробуйте повторить попытку чуть позже."
            ),
            parse_mode="HTML",
            reply_markup=build_workouts_keyboard([], include_create=True),
        )
        context.user_data["conversation_active"] = False
        return ConversationHandler.END

    description = (
        "🗂️ <b>Ваши тренировки</b>\n"
        "Выберите тренировку, чтобы посмотреть подробности, либо создайте новую."
    )
    await query.message.edit_text(
        description,
        parse_mode="HTML",
        reply_markup=build_workouts_keyboard(workouts),
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
            reply_markup=build_workouts_keyboard([], include_create=False),
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
            reply_markup=build_workouts_keyboard([], include_create=False),
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
            reply_markup=build_workouts_keyboard([], include_create=True),
        )
        context.user_data["conversation_active"] = False
        return ConversationHandler.END

    await query.message.edit_text(
        _format_workout_details(workout),
        parse_mode="HTML",
        reply_markup=get_workout_details_keyboard(),
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
            reply_markup=build_workouts_keyboard([], include_create=False),
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
            reply_markup=build_workouts_keyboard([], include_create=False),
        )
        context.user_data["conversation_active"] = False
        return ConversationHandler.END

    context.user_data[_WORKOUT_STAGE_KEY] = "name"
    context.user_data[_WORKOUT_DRAFT_KEY] = {}
    context.user_data[_WORKOUT_MESSAGE_IDS_KEY] = []

    message = await query.message.edit_text(
        (
            "📝 <b>Введите название тренировки</b>\n"
            "Например: <code>Грудь и плечи</code>."
        ),
        parse_mode="HTML",
    )
    context.user_data[_WORKOUT_MESSAGE_IDS_KEY].append(message.message_id)
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

    if stage is None or draft is None or token is None:
        await update.message.reply_text(
            "⚠️ Возникла ошибка. Попробуйте начать создание тренировки заново.",
        )
        context.user_data["conversation_active"] = False
        _reset_workout_flow(context)
        return ConversationHandler.END

    text = update.message.text.strip()
    chat_id = update.message.chat_id

    if stage == "name":
        draft["name"] = text
        context.user_data[_WORKOUT_STAGE_KEY] = "description"
        message = await update.message.reply_text(
            (
                "📝 <b>Добавьте описание тренировки</b>\n"
                "Например: <code>Силовая работа с акцентом на базовые упражнения</code>."
            ),
            parse_mode="HTML",
        )
        _remember_prompt(context, message.message_id, chat_id)
        return WORKOUT_CREATION

    if stage == "description":
        draft["description"] = text
        context.user_data[_WORKOUT_STAGE_KEY] = "date"
        message = await update.message.reply_text(
            (
                "📅 <b>Укажите дату тренировки</b> в формате"
                " <code>дд-мм-гггг</code>."
            ),
            parse_mode="HTML",
        )
        _remember_prompt(context, message.message_id, chat_id)
        return WORKOUT_CREATION

    if stage == "date":
        parsed_date = _parse_user_date(text)
        if not parsed_date:
            message = await update.message.reply_text(
                "⚠️ Неверный формат даты. Используйте <code>дд-мм-гггг</code>.",
                parse_mode="HTML",
            )
            _remember_prompt(context, message.message_id, chat_id)
            return WORKOUT_CREATION
        draft["date"] = parsed_date
        context.user_data[_WORKOUT_STAGE_KEY] = "duration"
        message = await update.message.reply_text(
            "⏱️ <b>Укажите длительность тренировки</b> в минутах.",
            parse_mode="HTML",
        )
        _remember_prompt(context, message.message_id, chat_id)
        return WORKOUT_CREATION

    if stage == "duration":
        if not text.isdigit() or int(text) <= 0:
            message = await update.message.reply_text(
                "⚠️ Введите целое число минут больше нуля.",
            )
            _remember_prompt(context, message.message_id, chat_id)
            return WORKOUT_CREATION
        draft["duration"] = int(text)
        context.user_data[_WORKOUT_STAGE_KEY] = "calories"
        message = await update.message.reply_text(
            "🔥 <b>Укажите потраченные калории</b> (целое число).",
            parse_mode="HTML",
        )
        _remember_prompt(context, message.message_id, chat_id)
        return WORKOUT_CREATION

    if stage == "calories":
        if not text.isdigit() or int(text) < 0:
            message = await update.message.reply_text(
                "⚠️ Калории вводятся целым числом не меньше нуля.",
            )
            _remember_prompt(context, message.message_id, chat_id)
            return WORKOUT_CREATION
        draft["calories"] = int(text)

        exercises = await _fetch_exercises(token)
        if exercises is None:
            await update.message.reply_text(
                "❌ Не удалось получить список упражнений. Попробуйте позже.",
            )
            context.user_data["conversation_active"] = False
            _reset_workout_flow(context)
            return ConversationHandler.END
        if not exercises:
            await update.message.reply_text(
                (
                    "📋 Сначала создайте хотя бы одно упражнение в разделе"
                    " «Упражнения», затем повторите создание тренировки."
                )
            )
            context.user_data["conversation_active"] = False
            _reset_workout_flow(context)
            return ConversationHandler.END

        context.user_data[_WORKOUT_STAGE_KEY] = "exercise"
        context.user_data[_WORKOUT_EXERCISES_KEY] = {
            exercise.get("uuid"): exercise for exercise in exercises if exercise.get("uuid")
        }
        keyboard = build_exercise_selection_keyboard(exercises)
        message = await update.message.reply_text(
            (
                "💪 <b>Выберите упражнение для тренировки</b>."
                " После выбора бот попросит указать вес, повторы и интенсивность."
            ),
            parse_mode="HTML",
            reply_markup=keyboard,
        )
        _remember_prompt(context, message.message_id, chat_id)
        return WORKOUT_CREATION

    if stage == "exercise":
        message = await update.message.reply_text(
            "ℹ️ Выберите упражнение, используя кнопки под предыдущим сообщением.",
        )
        _remember_prompt(context, message.message_id, chat_id)
        return WORKOUT_CREATION

    if stage == "weight":
        weight = _parse_number(text)
        if weight is None or weight <= 0:
            message = await update.message.reply_text(
                "⚠️ Вес указывается положительным числом. Пример: 60 или 60.5",
            )
            _remember_prompt(context, message.message_id, chat_id)
            return WORKOUT_CREATION
        counts = draft.setdefault("counts", {})
        counts["weight"] = weight
        context.user_data[_WORKOUT_STAGE_KEY] = "reps"
        message = await update.message.reply_text(
            "🔢 Укажите количество повторов для подхода (целое число).",
        )
        _remember_prompt(context, message.message_id, chat_id)
        return WORKOUT_CREATION

    if stage == "reps":
        if not text.isdigit() or int(text) <= 0:
            message = await update.message.reply_text(
                "⚠️ Повторы вводятся целым числом больше нуля.",
            )
            _remember_prompt(context, message.message_id, chat_id)
            return WORKOUT_CREATION
        counts = draft.setdefault("counts", {})
        counts["reps"] = int(text)
        context.user_data[_WORKOUT_STAGE_KEY] = "intensity"
        message = await update.message.reply_text(
            (
                "💥 Укажите степень интенсивности (например: <code>no-failure</code>,"
                " <code>muscle-failure</code>, <code>technical-failure</code>)."
                " Чтобы пропустить, отправьте <code>-</code>."
            ),
            parse_mode="HTML",
        )
        _remember_prompt(context, message.message_id, chat_id)
        return WORKOUT_CREATION

    if stage == "intensity":
        counts = draft.setdefault("counts", {})
        intensity = text.strip()
        if intensity and intensity != "-":
            counts["type"] = intensity.replace(" ", "-").lower()
        payload = _prepare_payload(draft)
        if payload is None:
            await update.message.reply_text(
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
            await update.message.reply_text(
                "❌ Не удалось создать тренировку. Попробуйте повторить попытку позже.",
            )
            context.user_data["conversation_active"] = False
            _reset_workout_flow(context)
            return ConversationHandler.END

        workouts = await _fetch_workouts(token) or []
        await update.message.reply_text(
            "✅ Тренировка успешно сохранена в Gym-Stat!",
            reply_markup=build_workouts_keyboard(workouts),
            parse_mode="HTML",
        )
        context.user_data["conversation_active"] = False
        _reset_workout_flow(context)
        return ConversationHandler.END

    await update.message.reply_text(
        "⚠️ Неизвестный шаг. Попробуйте начать заново.",
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
                exercise_choices.values()
            ),
        )
        return WORKOUT_CREATION

    draft["exerciseId"] = exercise_uuid
    context.user_data[_WORKOUT_STAGE_KEY] = "weight"

    await query.message.edit_text(
        (
            "⚖️ Введите вес для подхода. Можно указать дробное значение через"
            " точку."
        )
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


def _format_workout_details(workout: dict[str, Any]) -> str:
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
        parts.append("\n<b>Подходы:</b>")
        for idx, workout_set in enumerate(sets, start=1):
            exercise_id = workout_set.get("exerciseId") or "—"
            counts = workout_set.get("counts") or []
            parts.append(f"{idx}. Упражнение: {exercise_id}")
            for count_idx, count in enumerate(counts, start=1):
                reps = count.get("reps")
                weight = count.get("weight")
                intensity = count.get("type")
                line = f"   • Подход {count_idx}: {reps} повторов, вес {weight}"
                if intensity:
                    line += f", интенсивность: {intensity}"
                parts.append(line)
    else:
        parts.append("\nПодходы ещё не добавлены.")

    return "\n".join(parts)


def _parse_user_date(value: str) -> Optional[str]:
    try:
        parsed = datetime.strptime(value, "%d-%m-%Y")
    except ValueError:
        return None
    result = datetime.combine(parsed.date(), time.min)
    return result.isoformat(sep=" ")


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
    exercise_id = draft.get("exerciseId")
    counts: Dict[str, Any] = draft.get("counts", {})

    if not all([name, description, date_value, duration is not None, calories is not None, exercise_id]):
        return None
    reps = counts.get("reps")
    weight = counts.get("weight")
    if reps is None or weight is None:
        return None

    if isinstance(weight, float) and weight.is_integer():
        weight = int(weight)

    count_entry: Dict[str, Any] = {
        "reps": reps,
        "weight": weight,
    }
    if counts.get("type"):
        count_entry["type"] = counts["type"]

    payload = {
        "name": name,
        "description": description,
        "date": date_value,
        "duration": duration,
        "calories": calories,
        "sets": [
            {
                "exerciseId": exercise_id,
                "counts": [count_entry],
            }
        ],
    }
    return payload


def _reset_workout_flow(context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.pop(_WORKOUT_STAGE_KEY, None)
    context.user_data.pop(_WORKOUT_DRAFT_KEY, None)
    context.user_data.pop(_WORKOUT_MESSAGE_IDS_KEY, None)
    context.user_data.pop(_WORKOUT_EXERCISES_KEY, None)
    context.user_data.pop("workout_token", None)


def _remember_prompt(
    context: ContextTypes.DEFAULT_TYPE,
    message_id: int,
    chat_id: int,
    *,
    delay: int = 300,
) -> None:
    context.user_data.setdefault(_WORKOUT_MESSAGE_IDS_KEY, []).append(message_id)
    schedule_message_deletion(context, [message_id], chat_id, delay=delay)
