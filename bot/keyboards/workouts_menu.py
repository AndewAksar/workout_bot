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
    include_create: bool = True,
    include_exercises: bool = True,
) -> InlineKeyboardMarkup:
    """Constructs a keyboard for the workouts list."""
    keyboard: list[list[InlineKeyboardButton]] = []
    for workout in workouts:
        uuid = workout.get("uuid")
        if not uuid:
            continue
        label = _format_workout_label(workout.get("name"), workout.get("date"))
        if len(label) > 64:
            label = label[:63] + "…"
        keyboard.append([
            InlineKeyboardButton(label, callback_data=f"workout:view:{uuid}"),
        ])

    if include_create:
        keyboard.append([
            InlineKeyboardButton("➕ Создать тренировку", callback_data="workout:create"),
        ])

    if include_exercises:
        keyboard.append([
            InlineKeyboardButton("📋 Упражнения", callback_data="exercises_menu"),
        ])

    keyboard.append([
        InlineKeyboardButton("🔙 Назад", callback_data="main_menu"),
    ])
    return InlineKeyboardMarkup(keyboard)


def get_workout_details_keyboard() -> InlineKeyboardMarkup:
    """Keyboard shown on the workout details screen."""
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("🔙 К тренировкам", callback_data="workouts")]]
    )


def build_exercise_selection_keyboard(exercises: Iterable[dict]) -> InlineKeyboardMarkup:
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
        InlineKeyboardButton("🔙 Назад", callback_data="workouts"),
    ])
    return InlineKeyboardMarkup(keyboard)
