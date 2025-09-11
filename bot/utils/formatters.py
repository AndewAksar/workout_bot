# bot/utils/formatters.py
"""Вспомогательные функции форматирования данных."""


def format_gender(gender: str | None) -> str:
    """Возвращает локализованное представление пола."""
    if not gender:
        return "Не указан"
    gender_lower = gender.lower()
    if gender_lower in ("male", "мужской"):
        return "Мужской"
    if gender_lower in ("female", "женский"):
        return "Женский"
    return gender