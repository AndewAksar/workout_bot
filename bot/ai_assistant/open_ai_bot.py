# bot/ai_assistant/open_ai_bot.py
"""
Модуль: open_ai_bot
Описание: модуль содержит функции для взаимодействия с API OpenAI ChatGPT.
Он используется Telegram-ботом для получения ответов на пользовательские
запросы.
Зависимости:
- httpx: отправка HTTP-запросов к API OpenAI.
- time: реализация задержек при повторных попытках.
- typing: описание типов данных.
- bot.utils.logger: настройка и использование логирования.
- bot.config.settings: получение конфигурационных параметров.
"""

from typing import List, Dict
import time
import httpx

from bot.utils.logger import setup_logging
from bot.config.settings import (
    OPENAI_API_KEY,
    OPENAI_API_URL,
    OPENAI_MODEL,
)

logger = setup_logging()

def generate_chatgpt_response(
        messages: List[Dict[str, str]],
        model: str = OPENAI_MODEL,
        retries: int = 3,
        delay: float = 2.0,
) -> str:
    """Генерирует ответ от ChatGPT на основе списка сообщений.
    Args:
        messages: Список сообщений в формате
            ``[{"role": "system|user|assistant", "content": "текст"}, ...]``.
        model: Модель OpenAI, используемая для генерации ответа.
        retries: Количество повторных попыток при ошибке API.
        delay: Задержка между повторными попытками в секундах.
    Returns:
        str: Ответ от ChatGPT либо сообщение об ошибке.
    """

    if not OPENAI_API_KEY:
        logger.error("Переменная окружения OPENAI_API_KEY не задана.")
        return "Ошибка: отсутствует ключ API OpenAI."

    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {"model": model, "messages": messages}

    for attempt in range(retries):
        try:
            logger.info(
                "Отправка запроса к OpenAI (попытка %s/%s)",
                attempt + 1,
                retries,
            )
            response = httpx.post(
                OPENAI_API_URL, headers=headers, json=payload, timeout=60
            )
            logger.debug(
                "Ответ OpenAI: %s - %s", response.status_code, response.text
            )
            if response.status_code == 200:
                data = response.json()
                return data["choices"][0]["message"]["content"]
            if response.status_code >= 500 and attempt < retries - 1:
                logger.warning(
                    "Серверная ошибка OpenAI (%s). Повтор через %.1f сек.",
                    response.status_code,
                    delay,
                )
                time.sleep(delay)
                continue
            logger.error(
                "Ошибка API OpenAI: %s - %s",
                response.status_code,
                response.text,
            )
            return f"Ошибка: {response.status_code} - {response.text}"
        except Exception as exc:  # noqa: BLE001
            logger.error("Исключение при запросе к OpenAI: %s", exc)
            if attempt < retries - 1:
                time.sleep(delay)
            else:
                return f"Ошибка: {exc}"

    return "Ошибка: Не удалось получить ответ от OpenAI после нескольких попыток."

__all__ = ["generate_chatgpt_response"]