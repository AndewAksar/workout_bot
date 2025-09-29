# bot/keyboards/stats_menu.py
"""Клавиатура раздела статистики Gym-Stat."""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from bot.config.settings import GYMSTAT_WEB_URL


def _build_url(segment: str) -> str:
    """Формирует абсолютный URL до раздела статистики Gym-Stat."""
    base_url = GYMSTAT_WEB_URL.rstrip('/')
    return f"{base_url}/stats/{segment}".rstrip('/')


def get_stats_menu() -> InlineKeyboardMarkup:
    """Создаёт клавиатуру со ссылками на статистику Gym-Stat."""
    keyboard = [
        [
            InlineKeyboardButton(
                "По упражнениям",
                url=_build_url('exercises')
            )
        ],
        [
            InlineKeyboardButton(
                "По тренировкам",
                url=_build_url('workouts')
            )
        ],
        [
            InlineKeyboardButton(
                "По весу",
                url=_build_url('weight')
            )
        ],
        [
            InlineKeyboardButton(
                "🔙 Назад",
                callback_data='settings'
            )
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


__all__ = ["get_stats_menu"]
