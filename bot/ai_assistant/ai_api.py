# bot/handlers/ai_api.py
"""
Модуль: ai_api.py
Описание: Модуль содержит функции для взаимодействия с API GigaChat, включая получение токена
и генерацию ответов на пользовательские запросы.

Зависимости:
- requests: Для отправки HTTP-запросов к API GigaChat.
- uuid: Для генерации уникальных идентификаторов запросов.
- json: Для сериализации данных запроса в логи.
- time: Для реализации задержек при повторных попытках.
- bot.utils.logger: Для настройки логирования.
- bot.config.settings: Для получения конфигурационных переменных.
- bot.config.ai_prompt: Для получения системного предпромта.

Автор: Aksarin A.
Дата создания: 26/08/2025
"""

import requests
import uuid
import json
import time
import sqlite3

from bot.utils.logger import setup_logging
from bot.config.settings import (
    OAUTH_URL,
    GIGACHAT_API_URL,
    CLIENT_CREDENTIALS,
    DB_PATH
)
from bot.ai_assistant.ai_prompt import get_system_prompt


logger = setup_logging()

# Глобальная переменная для хранения токена
GIGACHAT_AUTH_TOKEN = None

# Глобальная переменная для хранения ID запроса
def get_gigachat_token() -> str:
    """
    Получает OAuth-токен для API GigaChat.
    Возвращаемое значение:
        str: Токен доступа для API GigaChat.
    Исключения:
        Exception: Если не удалось получить токен.
    """
    global GIGACHAT_AUTH_TOKEN
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Accept': 'application/json',
        'RqUID': str(uuid.uuid4()),
        'Authorization': f'Basic {CLIENT_CREDENTIALS}'
    }
    payload = {
        'scope': 'GIGACHAT_API_PERS'
    }
    try:
        logger.info("Получение токена через OAuth...")
        response = requests.post(OAUTH_URL, headers=headers, data=payload, verify=False)
        if response.status_code == 200:
            GIGACHAT_AUTH_TOKEN = response.json()['access_token']
            logger.info(f"Токен получен: {GIGACHAT_AUTH_TOKEN[:10]}...")
            return GIGACHAT_AUTH_TOKEN
        else:
            logger.error(f"Ошибка OAuth: {response.status_code} - {response.text}")
            raise Exception(f"Ошибка OAuth: {response.status_code} - {response.text}")
    except Exception as e:
        logger.error(f"Ошибка при получении токена: {e}")
        raise

def get_user_settings(user_id: int) -> dict:
    """
    Получает данные пользователя из базы данных по user_id.
    Аргументы:
        user_id (int): Идентификатор пользователя в Telegram.
    Возвращаемое значение:
        dict: Словарь с данными пользователя (name, age, weight, height, gender, username) или пустой dict, если данных нет.
    Исключения:
        sqlite3.Error: Если возникают ошибки при работе с базой данных.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute(
            '''
                SELECT name, age, weight, height, gender, username
                FROM UserSettings
                WHERE user_id = ?
            ''', (user_id,)
        )
        row = c.fetchone()
        if row:
            return {
                'name': row[0],
                'age': row[1],
                'weight': row[2],
                'height': row[3],
                'gender': row[4],
                'username': row[5]
            }
        else:
            logger.info(f"Данные для user_id {user_id} не найдены в БД.")
            return {}
    except sqlite3.Error as e:
        logger.error(f"Ошибка при получении данных пользователя из БД: {e}")
        return {}
    finally:
        if conn:
            conn.close()

def generate_gigachat_response(
        prompt: str,
        user_id: int,
        retries: int = 3,
        delay: float = 2.0
) -> str:
    """
    Генерирует ответ от GigaChat API на основе пользовательского запроса.
    Автоматически добавляет данные пользователя из БД в системный промпт.
    Аргументы:
        prompt (str): Текст пользовательского запроса.
        user_id (int): Идентификатор пользователя в Telegram для получения данных из БД.
        retries (int): Количество повторных попыток при ошибке API (по умолчанию 3).
        delay (float): Задержка в секундах между повторными попытками (по умолчанию 2.0).
    Возвращаемое значение:
        str: Ответ от GigaChat API или сообщение об ошибке.
    Исключения:
        Exception: Если запрос к API не удался после всех попыток.
    """
    global GIGACHAT_AUTH_TOKEN
    if not GIGACHAT_AUTH_TOKEN:
        get_gigachat_token()

    # Получаем данные пользователя из БД
    settings = get_user_settings(user_id)

    # Формируем дополнение к системному промпту с данными пользователя
    user_data_str = ""
    if settings:
        user_data_str = "\nДанные пользователя:\n"
        for key, value in settings.items():
            if value is not None:
                user_data_str += f"{key.capitalize()}: {value}\n"

    # Обновляем системный промпт
    system_prompt = get_system_prompt() + user_data_str

    headers = {
        'Authorization': f'Bearer {GIGACHAT_AUTH_TOKEN}',
        'Content-Type': 'application/json',
        'RqUID': str(uuid.uuid4())
    }
    data = {
        "model": "GigaChat",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 2500,
        "temperature": 0.7
    }
    for attempt in range(retries):
        try:
            logger.info(f"Отправка запроса (попытка {attempt + 1}/{retries}) с заголовком Authorization: Bearer {GIGACHAT_AUTH_TOKEN[:10]}...")
            logger.info(f"Отправляемый запрос: {json.dumps(data, ensure_ascii=False)}")
            response = requests.post(GIGACHAT_API_URL, json=data, headers=headers, verify=False)
            logger.info(f"Получен ответ: {response.status_code} - {response.text}")
            if response.status_code == 200:
                return response.json()['choices'][0]['message']['content']
            elif response.status_code == 401:
                logger.info("Токен недействителен, пытаемся получить новый...")
                get_gigachat_token()
                headers['Authorization'] = f'Bearer {GIGACHAT_AUTH_TOKEN}'
            elif response.status_code == 500:
                logger.warning(f"Внутренняя ошибка сервера (попытка {attempt + 1}/{retries}). Повтор через {delay} сек...")
                if attempt == retries - 1:
                    logger.error(f"Ошибка API GigaChat: {response.status_code} - {response.text}")
                    return "Ошибка: Внутренняя ошибка сервера. Попробуйте позже."
                time.sleep(delay)
            else:
                logger.error(f"Ошибка API GigaChat: {response.status_code} - {response.text}")
                return f"Ошибка: {response.status_code} - {response.text}"
        except Exception as e:
            logger.error(f"Ошибка API GigaChat: {e}")
            if attempt == retries - 1:
                return f"Ошибка: {str(e)}"
            time.sleep(delay)
    return "Ошибка: Не удалось получить ответ от сервера после нескольких попыток."
