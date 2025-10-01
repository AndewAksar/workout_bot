"""Inline keyboards for managing workouts."""
from __future__ import annotations

from datetime import datetime
from typing import Iterable, Sequence

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

_DATE_FORMATS: Sequence[str] = (
    "%Y-%m-%dT%H:%M:%S.%f%z",
    "%Y-%m-%dT%H:%M:%S%z",
    "%Y-%m-%dT%H:%M:%S.%f",
    "%Y-%m-%dT%H:%M:%S",
)


def _format_workout_label(name: str | None, date_value: str | None) -> str:
    """Builds a human friendly label for a workout button."""
    display_name = name or "Без названия"
    if not date_value:
        return display_name

    clean = date_value.strip()
    if clean.endswith("Z"):
        clean = clean[:-1] + "+00:00"

    for fmt in _DATE_FORMATS:
        try:
            parsed = datetime.strptime(clean, fmt)
        except ValueError:
            continue
        formatted = parsed.strftime("%d.%m.%Y")
        return f"{formatted} — {display_name}"

    return display_name


def build_workouts_keyboard(
    workouts: Iterable[dict],
    *,
    page: int,
    page_size: int,
    total_pages: int,
    include_create: bool = True,
    include_exercises: bool = True,
) -> InlineKeyboardMarkup:
    """Constructs a keyboard for the workouts list with pagination."""
    sanitized_page = page if page > 0 else 1
    sanitized_page_size = page_size if page_size > 0 else 1
    sanitized_total = total_pages if total_pages > 0 else 1

    workouts_list = list(workouts)
    start = (sanitized_page - 1) * sanitized_page_size
    end = start + sanitized_page_size
    page_items = workouts_list[start:end]

    keyboard: list[list[InlineKeyboardButton]] = []

    if include_create:
        keyboard.append([
            InlineKeyboardButton("➕", callback_data="workout:create"),
        ])

    workout_buttons: list[InlineKeyboardButton] = []
    for workout in page_items:
        uuid = workout.get("uuid")
        if not uuid:
            continue
        label = _format_workout_label(workout.get("name"), workout.get("date"))
        if len(label) > 64:
            label = label[:63] + "…"
        workout_buttons.append(
            InlineKeyboardButton(label, callback_data=f"workout:view:{uuid}")
        )

    for index in range(0, len(workout_buttons), 2):
        keyboard.append(workout_buttons[index : index + 2])

    if sanitized_total > 1:
        navigation_row: list[InlineKeyboardButton] = []
        if sanitized_page > 1:
            navigation_row.append(
                InlineKeyboardButton(
                    "◀️ Предыдущая страница",
                    callback_data=f"workouts:page:{sanitized_page - 1}",
                )
            )
        if sanitized_page < sanitized_total:
            navigation_row.append(
                InlineKeyboardButton(
                    "▶️ Следующая страница",
                    callback_data=f"workouts:page:{sanitized_page + 1}",
                )
            )
        if navigation_row:
            keyboard.append(navigation_row)

    keyboard.append([
        InlineKeyboardButton("🔙 Назад", callback_data="main_menu"),
    ])
    return InlineKeyboardMarkup(keyboard)


def get_workout_details_keyboard(uuid: str, page: int) -> InlineKeyboardMarkup:
    """Keyboard shown on the workout details screen."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "🗑️ Удалить тренировку",
                    callback_data=f"workout:delete_prompt:{uuid}",
                )
            ],
            [
                InlineKeyboardButton(
                    "🔙 К тренировкам",
                    callback_data=f"workouts:page:{page if page > 0 else 1}",
                )
            ],
        ]
    )


def get_workout_delete_keyboard(uuid: str) -> InlineKeyboardMarkup:
    """Keyboard shown when confirming workout deletion."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "Да, удалить", callback_data=f"workout:delete_confirm:{uuid}"
                ),
                InlineKeyboardButton(
                    "Отмена", callback_data=f"workout:view:{uuid}"
                ),
            ]
        ]
    )


def build_add_set_keyboard() -> InlineKeyboardMarkup:
    """Keyboard that prompts the user to add another workout set."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Да", callback_data="workout:add_set:yes"),
                InlineKeyboardButton("Нет", callback_data="workout:add_set:no"),
            ]
        ]
    )


def build_exercise_selection_keyboard(
    exercises: Iterable[dict],
    *,
    page: int = 1,
) -> InlineKeyboardMarkup:
    """Keyboard that allows choosing an exercise for a workout set."""
    keyboard: list[list[InlineKeyboardButton]] = []
    for exercise in exercises:
        uuid = exercise.get("uuid")
        if not uuid:
            continue
        label = exercise.get("name") or "Без названия"
        keyboard.append([
            InlineKeyboardButton(label, callback_data=f"workout:select_exercise:{uuid}"),
        ])

    keyboard.append([
        InlineKeyboardButton(
            "🔙 Назад", callback_data=f"workouts:page:{page if page > 0 else 1}"
        ),
    ])
    return InlineKeyboardMarkup(keyboard)
