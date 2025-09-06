# bot/keyboards/settings_menu.py
"""
Модуль: settings_menu.py
Описание: Модуль содержит функции для создания интерактивных клавиатур Telegram-бота,
используемых для меню настроек. Клавиатура создается с использованием
InlineKeyboardButton и InlineKeyboardMarkup из библиотеки python-telegram-bot.

Зависимости:
- telegram: Для создания интерактивных кнопок и клавиатур (InlineKeyboardButton, InlineKeyboardMarkup).
"""

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup
)


def get_settings_menu():
    keyboard = [
        [
            InlineKeyboardButton(
                "📋 Личные данные", callback_data='personal_data'
            ),
            InlineKeyboardButton(
                "🏋️ Тренировки", callback_data='training_settings'
            )
        ],
        [
            InlineKeyboardButton(
                "👤 Показать профиль", callback_data='show_profile'
            )
        ],
        [
            InlineKeyboardButton(
                "🔙 Назад в главное меню", callback_data='main_menu'
            )
        ]
    ]
    return InlineKeyboardMarkup(keyboard)