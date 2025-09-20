# bot/keyboards/personal_data_menu.py
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def get_personal_data_menu():
    keyboard = [
        [
            InlineKeyboardButton(
                "Имя", callback_data='set_name'
            )
        ],
        [
            InlineKeyboardButton(
                "Пол", callback_data='set_gender'
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
                "📊 Параметры тела", callback_data='body_params'
            ),
            InlineKeyboardButton(
                "🔙 Назад", callback_data='settings'
            )
        ],

    ]
    return InlineKeyboardMarkup(keyboard)