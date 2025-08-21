# bot/keyboards/personal_data_menu.py
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def get_personal_data_menu():
    keyboard = [
        [
            InlineKeyboardButton(
                "Имя", callback_data='set_name'
            ),
            InlineKeyboardButton(
                "Возраст", callback_data='set_age'
            )
        ],
        [
            InlineKeyboardButton(
                "Вес", callback_data='set_weight'
            ),
            InlineKeyboardButton(
                "Рост", callback_data='set_height'
            )
        ],
        [
            InlineKeyboardButton(
                "🔙 Назад", callback_data='settings'
            )
        ]
    ]
    return InlineKeyboardMarkup(keyboard)