# bot/keyboards/main_menu.py
"""
Модуль: main_menu.py
Описание: Модуль содержит функции для создания интерактивных клавиатур Telegram-бота,
используемых в главном меню и меню настроек. Клавиатуры создаются с использованием
InlineKeyboardButton и InlineKeyboardMarkup из библиотеки python-telegram-bot.

Зависимости:
- telegram: Для создания интерактивных кнопок и клавиатур (InlineKeyboardButton, InlineKeyboardMarkup).
"""

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup
)


def get_main_menu(mode: str = "local"):
    """
    Создает главное меню бота.
    Описание:
        Формирует интерактивную клавиатуру с кнопками для основных функций бота:
        начать тренировку, просмотр тренировок, вызов AI-консультанта,
        смену режима работы и доступ к настройкам.
    Аргументы:
        Нет
    Возвращаемое значение:
        InlineKeyboardMarkup: Объект клавиатуры с пятью кнопками для главного меню.
    Пример использования:
        >>> keyboard = get_main_menu()
        [Возвращается InlineKeyboardMarkup с кнопками главного меню]
    """
    keyboard = [
        [
            InlineKeyboardButton("🏋️‍♂️ Начать тренировку", callback_data='start_training'),
            InlineKeyboardButton("🗂️ Тренировки", callback_data='workouts')
        ],
        [
            InlineKeyboardButton("📋 Упражнения", callback_data='exercises_menu'),
            InlineKeyboardButton("🔄 Сменить режим", callback_data='switch_mode')
        ],
        [
            InlineKeyboardButton("🤖 AI-консультант", callback_data='my_ai_assistant'),
            InlineKeyboardButton("⚙️ Настройки", callback_data='settings')
        ]
    ]
    if mode == "api":
        keyboard.append(
            [
                InlineKeyboardButton(
                    "🌐 Открыть Gym-Stat.ru",
                    url="https://gym-stat.ru"
                )
            ]
        )
    return InlineKeyboardMarkup(keyboard)