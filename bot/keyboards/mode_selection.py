# bot/keyboards/mode_selection.py
"""
Модуль: mode_selection.py
Описание: Содержит клавиатуры для выбора режима работы бота.
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def get_mode_selection_keyboard() -> InlineKeyboardMarkup:
    """Возвращает клавиатуру для выбора режима работы."""
    keyboard = [
        [
            InlineKeyboardButton("📱 Telegram-версия", callback_data="select_mode_local"),
            InlineKeyboardButton("🌐 Интеграция с Gym-Stat.ru", callback_data="select_mode_api")
        ],
        [
            InlineKeyboardButton("❓ Помощь", callback_data="show_help")
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_api_auth_keyboard() -> InlineKeyboardMarkup:
    """Возвращает клавиатуру с вариантами авторизации через Gym-Stat."""
    keyboard = [
        [
            InlineKeyboardButton("🔐 Войти", callback_data="login"),
            InlineKeyboardButton("📝 Регистрация", callback_data="register")
        ],
        [
            InlineKeyboardButton("🔙 Назад", callback_data='switch_mode')
        ]
    ]
    return InlineKeyboardMarkup(keyboard)