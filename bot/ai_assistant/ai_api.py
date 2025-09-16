# bot/handlers/ai_api.py
"""
Модуль: ai_api.py
Описание: Модуль содержит функции для взаимодействия с API GigaChat, включая получение токена
и генерацию ответов на пользовательские запросы.

Зависимости:
- requests: Для отправки HTTP-запросов к API GigaChat.
- uuid: Для генерации уникальных идентификаторов запросов.
- json: Для сериализации данных запроса в логи.
- asyncio: Для неблокирующих задержек при повторных попытках.
- httpx: Для асинхронной отправки HTTP-запросов к API GigaChat.
- bot.utils.logger: Для настройки логирования.
- bot.config.settings: Для получения конфигурационных переменных.
- bot.config.ai_prompt: Для получения системного предпромта.
"""

import asyncio
import json
import uuid

import httpx
import requests
import aiosqlite


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


async def get_user_settings(user_id: int) -> dict:
    """
    Получает данные пользователя из базы данных по user_id.
    Аргументы:
        user_id (int): Идентификатор пользователя в Telegram.
    Возвращаемое значение:
        dict: Словарь с данными пользователя (name, age, weight, height, gender, username) или пустой dict, если данных нет.
    Исключения:
        aiosqlite.Error: Если возникают ошибки при работе с базой данных.
    """
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
            """
                SELECT name, age, weight, height, gender, username
                FROM UserSettings
                WHERE user_id = ?
            """,
                (user_id,),
            ) as cursor:
                row = await cursor.fetchone()
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
    except aiosqlite.Error as e:
        logger.error(f"Ошибка при получении данных пользователя из БД: {e}")
        return {}


async def generate_gigachat_response(
        messages: list,
        retries: int = 3,
        delay: float = 2.0
) -> str:
    """
    Генерирует ответ от GigaChat API на основе списка сообщений.
    Аргументы:
        messages (list): Список сообщений в формате [{'role': 'system/user/assistant', 'content': 'text'}].
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

    headers = {
        'Authorization': f'Bearer {GIGACHAT_AUTH_TOKEN}',
        'Content-Type': 'application/json',
        'RqUID': str(uuid.uuid4())
    }
    data = {
        "model": "GigaChat",
        "messages": messages,
        "max_tokens": 2500,
        "temperature": 0.7
    }

    headers = {
        'Authorization': f'Bearer {GIGACHAT_AUTH_TOKEN}',
        'Content-Type': 'application/json',
        'RqUID': str(uuid.uuid4())
    }
    data = {
        "model": "GigaChat",
        "messages": messages,
        "max_tokens": 2500,
        "temperature": 0.7
    }


    async with httpx.AsyncClient(verify=False, timeout=60) as client:
        for attempt in range(retries):
            try:
                token_preview = (GIGACHAT_AUTH_TOKEN or "")[:10]
                logger.info(
                    "Отправка запроса (попытка %s/%s) с заголовком Authorization: Bearer %s...",
                    attempt + 1,
                    retries,
                    token_preview,
                )
                logger.info(
                    "Отправляемый запрос: %s",
                    json.dumps(data, ensure_ascii=False),
                )
                response = await client.post(
                    GIGACHAT_API_URL,
                    json=data,
                    headers=headers,
                )
                logger.info(
                    "Получен ответ: %s - %s",
                    response.status_code,
                    response.text,
                )
                if response.status_code == 200:
                    return response.json()['choices'][0]['message']['content']
                if response.status_code == 401:
                    logger.info("Токен недействителен, пытаемся получить новый...")
                    get_gigachat_token()
                    headers['Authorization'] = f'Bearer {GIGACHAT_AUTH_TOKEN}'
                    continue
                if response.status_code == 500:
                    logger.warning(
                        "Внутренняя ошибка сервера (попытка %s/%s). Повтор через %.1f сек...",
                        attempt + 1,
                        retries,
                        delay,
                    )
                    if attempt == retries - 1:
                        logger.error(
                            "Ошибка API GigaChat: %s - %s",
                            response.status_code,
                            response.text,
                        )
                        return "Ошибка: Внутренняя ошибка сервера. Попробуйте позже."
                    await asyncio.sleep(delay)
                    continue
                logger.error(
                    "Ошибка API GigaChat: %s - %s",
                    response.status_code,
                    response.text,
                )
                return f"Ошибка: {response.status_code} - {response.text}"
            except Exception as e:  # noqa: BLE001
                logger.error(f"Ошибка API GigaChat: {e}")
                if attempt == retries - 1:
                    return f"Ошибка: {str(e)}"
                await asyncio.sleep(delay)
    return "Ошибка: Не удалось получить ответ от сервера после нескольких попыток."
