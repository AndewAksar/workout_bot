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
from cryptography.fernet import Fernet


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

# Базовый URL API Gym-Stat
GYMSTAT_API_URL = environ.get('GYMSTAT_API_URL', 'https://api.gym-stat.ru')
# Ключ для шифрования токенов
ENCRYPT_KEY = environ.get('ENCRYPT_KEY', Fernet.generate_key().decode())
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
(
    SET_NAME,
    SET_AGE,
    SET_WEIGHT,
    SET_HEIGHT,
    SET_GENDER,
    AI_CONSULTATION,
    SET_BODY_PARAM,
    EXERCISE_GROUP_SET_NAME,
    EXERCISE_GROUP_SET_DESCRIPTION,
    EXERCISE_GROUP_RENAME,
    EXERCISE_GROUP_UPDATE_DESCRIPTION,
    EXERCISE_SET_NAME,
    EXERCISE_SET_DESCRIPTION,
    EXERCISE_RENAME,
    EXERCISE_UPDATE_DESCRIPTION,
    WORKOUT_CREATION,
) = range(16)
"""
Константы состояний ConversationHandler:
- SET_NAME, SET_AGE, SET_WEIGHT, SET_HEIGHT, SET_GENDER — ввод персональных данных;
- AI_CONSULTATION — диалог с AI-консультантом;
- SET_BODY_PARAM — ввод параметров тела;
- EXERCISE_GROUP_SET_NAME, EXERCISE_GROUP_SET_DESCRIPTION — создание группы упражнений;
- EXERCISE_GROUP_RENAME, EXERCISE_GROUP_UPDATE_DESCRIPTION — редактирование группы упражнений;
- EXERCISE_SET_NAME, EXERCISE_SET_DESCRIPTION — создание упражнения;
- EXERCISE_RENAME, EXERCISE_UPDATE_DESCRIPTION — редактирование упражнения.
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