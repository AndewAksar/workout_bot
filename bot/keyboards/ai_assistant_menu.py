# bot/keyboards/ai_assistant_menu.py
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def get_ai_assistant_menu():
    keyboard = [
        [
            InlineKeyboardButton(
                "💬 Получить консультацию у AI-консультанта", callback_data='start_ai_assistant'
            )
        ],
        [
            InlineKeyboardButton(
                "🔙 Назад", callback_data='settings'
            )
        ]
    ]
    return InlineKeyboardMarkup(keyboard)