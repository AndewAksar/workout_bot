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


def build_exercises_keyboard(
    exercises: Iterable[dict],
    *,
    page: int = 1,
    page_size: int = 4,
    total_pages: int = 1,
) -> InlineKeyboardMarkup:
    """Формирует клавиатуру со списком упражнений с учётом пагинации."""
    keyboard: list[list[InlineKeyboardButton]] = []

    exercises_list = [exercise for exercise in exercises if isinstance(exercise, dict)]
    if page_size <= 0:
        page_size = 1
    if total_pages < 1:
        total_pages = 1
    page = max(1, min(page, total_pages))
    start = (page - 1) * page_size
    end = start + page_size

    for exercise in exercises_list[start:end]:
        uuid = exercise.get("uuid")
        if not uuid:
            continue
        name = exercise.get("name") or "Без названия"
        keyboard.append(
            [InlineKeyboardButton(_shorten(str(name)), callback_data=f"exercise:view:{uuid}")]
        )

    keyboard.append([InlineKeyboardButton("➕ Создать упражнение", callback_data="exercise:create")])

    navigation_row: list[InlineKeyboardButton] = []
    if total_pages > 1 and page > 1:
        navigation_row.append(
            InlineKeyboardButton("⬅️", callback_data=f"exercise_list:page:{page - 1}")
        )
    if total_pages > 1 and page < total_pages:
        navigation_row.append(
            InlineKeyboardButton("➡️", callback_data=f"exercise_list:page:{page + 1}")
        )
    if navigation_row:
        keyboard.append(navigation_row)

    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="exercises_menu")])
    return InlineKeyboardMarkup(keyboard)


def build_exercise_groups_keyboard(
    groups: Iterable[dict],
    *,
    page: int = 1,
    total_pages: int = 1,
) -> InlineKeyboardMarkup:
    """Создаёт клавиатуру со списком групп упражнений с учётом пагинации."""
    keyboard: list[list[InlineKeyboardButton]] = [
        [InlineKeyboardButton("➕", callback_data="exercise_group:create")]
    ]

    group_buttons: list[InlineKeyboardButton] = []
    for group in groups:
        if not isinstance(group, dict):
            continue
        uuid = group.get("uuid")
        if not uuid:
            continue
        name = group.get("name") or "Без названия"
        group_buttons.append(
            InlineKeyboardButton(
                _shorten(str(name)), callback_data=f"exercise_group:view:{uuid}"
            )
        )

    for index in range(0, len(group_buttons), 2):
        keyboard.append(group_buttons[index : index + 2])

    navigation_row: list[InlineKeyboardButton] = []
    if total_pages > 1 and page > 1:
        navigation_row.append(
            InlineKeyboardButton(
                "◀️", callback_data=f"exercise_groups:page:{page - 1}"
            )
        )
    if total_pages > 1 and page < total_pages:
        navigation_row.append(
            InlineKeyboardButton(
                "▶️", callback_data=f"exercise_groups:page:{page + 1}"
            )
        )
    if navigation_row:
        keyboard.append(navigation_row)
    keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="exercises_menu")])
    return InlineKeyboardMarkup(keyboard)


def get_exercise_actions_keyboard(uuid: str) -> InlineKeyboardMarkup:
    """Возвращает клавиатуру управления конкретным упражнением."""
    keyboard = [
        [InlineKeyboardButton("✏️ Переименовать", callback_data=f"exercise:rename:{uuid}")],
        [InlineKeyboardButton("📝 Изменить описание", callback_data=f"exercise:description:{uuid}")],
        [InlineKeyboardButton("📂 Сменить группу", callback_data=f"exercise:change_group:{uuid}")],
        [InlineKeyboardButton("🗑️ Удалить", callback_data=f"exercise:ask_delete:{uuid}")],
        [InlineKeyboardButton("🔙 К списку упражнений", callback_data="exercise_list")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_exercise_delete_keyboard(uuid: str) -> InlineKeyboardMarkup:
    """Клавиатура подтверждения удаления упражнения."""
    keyboard = [
        [InlineKeyboardButton("✅ Удалить", callback_data=f"exercise:delete:{uuid}")],
        [InlineKeyboardButton("↩️ Отмена", callback_data=f"exercise:view:{uuid}")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_exercise_group_actions_keyboard(uuid: str, *, page: int = 1) -> InlineKeyboardMarkup:
    """Возвращает клавиатуру управления конкретной группой упражнений."""
    if page <= 1:
        back_callback = "exercise_groups"
    else:
        back_callback = f"exercise_groups:page:{page}"
    keyboard = [
        [InlineKeyboardButton("✏️ Переименовать", callback_data=f"exercise_group:rename:{uuid}")],
        [InlineKeyboardButton(
            "📝 Изменить описание", callback_data=f"exercise_group:description:{uuid}"
        )],
        [InlineKeyboardButton("🗑️ Удалить", callback_data=f"exercise_group:ask_delete:{uuid}")],
        [InlineKeyboardButton("⬅️ К списку", callback_data=back_callback)],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_exercise_group_delete_keyboard(uuid: str) -> InlineKeyboardMarkup:
    """Клавиатура подтверждения удаления группы упражнений."""
    keyboard = [
        [InlineKeyboardButton("✅ Удалить", callback_data=f"exercise_group:delete:{uuid}")],
        [InlineKeyboardButton("↩️ Отмена", callback_data=f"exercise_group:view:{uuid}")],
    ]
    return InlineKeyboardMarkup(keyboard)


def build_exercise_group_selection_keyboard(groups: Iterable[dict]) -> InlineKeyboardMarkup:
    """Клавиатура выбора группы при создании упражнения."""
    keyboard: list[list[InlineKeyboardButton]] = []
    for index, group in enumerate(groups):
        if not isinstance(group, dict):
            continue
        uuid = group.get("uuid")
        if not uuid:
            continue
        name = group.get("name") or "Без названия"
        keyboard.append(
            [
                InlineKeyboardButton(
                    _shorten(str(name)), callback_data=f"ex:sgc:{index}"
                )
            ]
        )
    keyboard.append([InlineKeyboardButton("↩️ Отмена", callback_data="exercise:create:cancel")])
    return InlineKeyboardMarkup(keyboard)


def build_exercise_group_update_keyboard(
    exercise_uuid: str, groups: Iterable[dict]
) -> InlineKeyboardMarkup:
    """Клавиатура выбора группы при изменении упражнения."""
    keyboard: list[list[InlineKeyboardButton]] = []
    for index, group in enumerate(groups):
        if not isinstance(group, dict):
            continue
        group_uuid = group.get("uuid")
        if not group_uuid:
            continue
        name = group.get("name") or "Без названия"
        keyboard.append(
            [
                InlineKeyboardButton(
                    _shorten(str(name)), callback_data=f"ex:sgu:{index}"
                )
            ]
        )
    keyboard.append([InlineKeyboardButton("↩️ Отмена", callback_data=f"exercise:view:{exercise_uuid}")])
    return InlineKeyboardMarkup(keyboard)
