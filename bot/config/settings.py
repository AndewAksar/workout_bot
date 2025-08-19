# bot/config/settings.py
from os import environ
from dotenv import load_dotenv


load_dotenv()

TELEGRAM_TOKEN = environ.get('TELEGRAM_TOKEN')

WELCOME_MESSAGE = (
    "💪 Добро пожаловать в бот для тренировок!\n"
    "Выберите действие в меню ниже:"
)