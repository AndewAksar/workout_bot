# bot/keyboards/body_params_menu.py
"""Inline-клавиатура для управления обмерами тела."""

from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


BODY_PARAM_BUTTONS: list[tuple[str, str]] = [
    ("Шея", "body_param_neck"),
    ("Талия", "body_param_waist"),
    ("Предплечье", "body_param_forearm"),
    ("Запястье", "body_param_wrist"),
    ("Бёдра", "body_param_hips"),
    ("Бедро", "body_param_thigh"),
    ("Икра", "body_param_calf"),
]


def get_body_params_menu(has_data: bool = False) -> InlineKeyboardMarkup:
    """Возвращает клавиатуру с параметрами тела."""

    keyboard: list[list[InlineKeyboardButton]] = []

    for i in range(0, len(BODY_PARAM_BUTTONS), 2):
        row_buttons = []
        for title, callback_data in BODY_PARAM_BUTTONS[i : i + 2]:
            row_buttons.append(InlineKeyboardButton(title, callback_data=callback_data))
        keyboard.append(row_buttons)

    if has_data:
        keyboard.append([
            InlineKeyboardButton("🗑️ Удалить данные", callback_data="delete_body_params")
        ])

    keyboard.append([
        InlineKeyboardButton("🔙 Назад", callback_data="personal_data")
    ])

    return InlineKeyboardMarkup(keyboard)