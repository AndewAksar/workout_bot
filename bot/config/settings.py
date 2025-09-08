# bot/config/settings.py
"""
Модуль: settings.py
Описание: Модуль содержит конфигурационные настройки для Telegram-бота, включая загрузку переменных окружения
и определение констант, используемых в приложении. Переменные окружения загружаются из файла .env
с использованием библиотеки python-dotenv.

Зависимости:
- os: Для работы с переменными окружения.
- dotenv: Для загрузки переменных из файла .env.
"""

import os
from os import environ
from dotenv import load_dotenv


# Загрузка переменных окружения из файла .env
load_dotenv()

# Настройки для OAuth
OAUTH_URL = environ.get('OAUTH_URL')
GIGACHAT_API_URL = environ.get('GIGACHAT_API_URL')
CLIENT_CREDENTIALS = environ.get('CLIENT_CREDENTIALS')
"""
str: Конфигурация OAuth для авторизации в Sberbank API.
Необходима для взаимодействия с API Sberbank.
"""

# Токен Telegram-бота, полученный из переменной окружения
TELEGRAM_TOKEN = environ.get('TELEGRAM_TOKEN')
"""
str: Токен для аутентификации Telegram-бота.
Получается из переменной окружения TELEGRAM_TOKEN.
Если переменная не задана, возвращается None.
Пример: "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
"""

# Приветственное сообщение, отображаемое пользователю при запуске бота
WELCOME_MESSAGE = (
    "💪 Добро пожаловать в бот для тренировок!\n"
    "Выберите действие в меню ниже:"
)
"""
str: Текст приветственного сообщения, отправляемого пользователю при выполнении команды /start.
Содержит эмодзи и инструкцию для взаимодействия с ботом.
"""

# Путь к базе данных
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'database', 'users.db')
"""
str: Путь к файлу базы данных, используемой ботом. Во избежании конфликтов с другими частями приложения.
"""

# Определение состояний для ConversationHandler.
# Используется для управления диалогами при вводе данных пользователем.
SET_NAME, SET_AGE, SET_WEIGHT, SET_HEIGHT, SET_GENDER, AI_CONSULTATION = range(6)
"""
Константы: SET_NAME, SET_AGE, SET_WEIGHT, SET_HEIGHT, SET_GENDER, AI_CONSULTATION
Описание: Состояния ConversationHandler для обработки ввода имени, возраста, веса,
роста и пола пользователя.
Значения: Целые числа от 0 до 5, представляющие этапы диалога.
"""

# Список допустимых команд бота.
VALID_COMMANDS = [
    "/start",
    "/help",
    "/cancel",
    "/contacts",
    "/settings",
]

# Настройки для работы с OpenAI
OPENAI_API_KEY = environ.get('OPENAI_API_KEY')
"""
str | None: API-ключ для доступа к сервису OpenAI.
Получается из переменной окружения ``OPENAI_API_KEY``.
Если переменная не задана, функции, использующие OpenAI, вернут ошибку.
"""

OPENAI_API_URL = environ.get('OPENAI_API_URL', 'https://api.openai.com/v1/chat/completions')
"""
str: Базовый URL для обращения к ChatGPT API.
По умолчанию используется ``https://api.openai.com/v1/chat/completions``.
"""

OPENAI_MODEL = environ.get('OPENAI_MODEL', 'gpt-4o-mini')
"""
str: Модель ChatGPT, применяемая по умолчанию для генерации ответов.
"""