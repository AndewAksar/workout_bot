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


def get_settings_menu(mode: str = "local"):
    keyboard = [
        [
            InlineKeyboardButton("📋 Личные данные", callback_data='personal_data'),
            InlineKeyboardButton("👤 Показать профиль", callback_data='show_profile')
        ]
    ]

    if mode == "api":
        keyboard.append([
            InlineKeyboardButton("📏 Мои параметры", callback_data="body_params")
        ])
        keyboard.append([
            InlineKeyboardButton("📊 Статистика", callback_data='statistics')
        ])
        keyboard.append([
            InlineKeyboardButton(
                "⚖️ Данные взвешивания",
                callback_data='weight_data_page_1'
            )
        ])
    else:
        keyboard.append([
            InlineKeyboardButton(
                "⚖️ Данные взвешивания",
                callback_data='weight_data_page_1'
            )
        ])
    keyboard.append([
        InlineKeyboardButton(
            "🔙 Назад в главное меню", callback_data='main_menu'
        )
    ])
    return InlineKeyboardMarkup(keyboard)