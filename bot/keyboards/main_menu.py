# bot/keyboards/main_menu.py
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def get_main_menu():
    keyboard = [
        [InlineKeyboardButton("🏋️‍♂️ Начать тренировку", callback_data='start_training')],
        [InlineKeyboardButton("🗂️ Мои тренировки", callback_data='my_trainings')],
        [InlineKeyboardButton("⚙️ Настройки", callback_data='settings')]
    ]
    return InlineKeyboardMarkup(keyboard)