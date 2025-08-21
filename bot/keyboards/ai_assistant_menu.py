# bot/keyboards/ai_assistant_menu.py
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def get_ai_assistant_menu():
    keyboard = [
        [
            InlineKeyboardButton(
                "💬 Получить общую консультацию у AI-консультанта", callback_data='set_training_type'
            )
        ],
        [
            InlineKeyboardButton(
                "🍴 Расписать диету", callback_data='set_training_type'
            )
        ],
        [
            InlineKeyboardButton(
                "📈 Разработать план тренировок", callback_data='set_training_type'
            )
        ],
        [
            InlineKeyboardButton(
                "🔙 Назад", callback_data='settings'
            )
        ]
    ]
    return InlineKeyboardMarkup(keyboard)