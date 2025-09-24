"""Inline-клавиатуры для раздела "Мои упражнения"."""

from __future__ import annotations

from typing import Iterable

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


_MAX_GROUP_TITLE = 32


def _shorten(text: str, limit: int = _MAX_GROUP_TITLE) -> str:
    """Обрезает подпись кнопки, если она длиннее допустимого лимита."""
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)] + "…"


def get_exercises_menu() -> InlineKeyboardMarkup:
    """Возвращает клавиатуру раздела "Мои упражнения"."""
    keyboard = [
        [InlineKeyboardButton("📋 Упражнения", callback_data="exercise_list")],
        [InlineKeyboardButton("🗂️ Группы упражнений", callback_data="exercise_groups")],
        [InlineKeyboardButton("🔙 Назад", callback_data="main_menu")],
    ]
    return InlineKeyboardMarkup(keyboard)


def build_exercise_groups_keyboard(groups: Iterable[dict]) -> InlineKeyboardMarkup:
    """Создаёт клавиатуру со списком групп упражнений."""
    keyboard: list[list[InlineKeyboardButton]] = []
    for group in groups:
        if not isinstance(group, dict):
            continue
        uuid = group.get("uuid")
        if not uuid:
            continue
        name = group.get("name") or "Без названия"
        keyboard.append(
            [InlineKeyboardButton(_shorten(str(name)), callback_data=f"exercise_group:view:{uuid}")]
        )
    keyboard.append([InlineKeyboardButton("➕ Создать группу", callback_data="exercise_group:create")])
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="exercises_menu")])
    return InlineKeyboardMarkup(keyboard)


def get_exercise_group_actions_keyboard(uuid: str) -> InlineKeyboardMarkup:
    """Возвращает клавиатуру управления конкретной группой упражнений."""
    keyboard = [
        [InlineKeyboardButton("✏️ Переименовать", callback_data=f"exercise_group:rename:{uuid}")],
        [InlineKeyboardButton(
            "📝 Изменить описание", callback_data=f"exercise_group:description:{uuid}"
        )],
        [InlineKeyboardButton("🗑️ Удалить", callback_data=f"exercise_group:ask_delete:{uuid}")],
        [InlineKeyboardButton("🔙 К списку групп", callback_data="exercise_groups")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_exercise_group_delete_keyboard(uuid: str) -> InlineKeyboardMarkup:
    """Клавиатура подтверждения удаления группы упражнений."""
    keyboard = [
        [InlineKeyboardButton("✅ Удалить", callback_data=f"exercise_group:delete:{uuid}")],
        [InlineKeyboardButton("↩️ Отмена", callback_data=f"exercise_group:view:{uuid}")],
    ]
    return InlineKeyboardMarkup(keyboard)
