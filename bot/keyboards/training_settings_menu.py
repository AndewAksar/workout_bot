# bot/keyboards/training_settings_menu.py
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def get_training_settings_menu():
    keyboard = [
        [
            InlineKeyboardButton(
                "💪 Тип тренировок", callback_data='set_training_type'
            )
        ],
        [
            InlineKeyboardButton(
                "🔙 Назад", callback_data='settings'
            )
        ]
    ]
    return InlineKeyboardMarkup(keyboard)