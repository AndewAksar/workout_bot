# bot/api/gym_stat_client.py
"""
Модуль: gym_stat_client.py
Описание: Асинхронный клиент для взаимодействия с REST API Gym-Stat.ru.
Зависимости:
- httpx: Для выполнения HTTP-запросов.
- typing: Для аннотаций типов.
- bot.config.settings: Для получения базового URL API.
- bot.utils.logger: Для логирования.
"""

from typing import Any, Dict, Optional

import httpx

from bot.config.settings import GYMSTAT_API_URL
from bot.utils.logger import setup_logging

logger = setup_logging()


async def _request(method: str, endpoint: str, token: Optional[str] = None,
                   json: Optional[Dict[str, Any]] = None,
                   params: Optional[Dict[str, Any]] = None) -> httpx.Response:
    """Внутренняя функция для выполнения HTTP-запроса."""
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    url = f"{GYMSTAT_API_URL}{endpoint}"
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.request(method, url, headers=headers, json=json, params=params)
    if resp.status_code >= 400:
        logger.warning(f"%s %s -> %s: %s", method, url, resp.status_code, resp.text)
    else:
        logger.debug(f"{method} {url} -> {resp.status_code}")
    return resp


async def register_user(payload: Dict[str, Any]) -> httpx.Response:
    """Регистрация нового пользователя."""
    # Согласно актуальной документации, регистрация выполняется по маршруту
    # ``/api/users/register`` и требует передачи полного набора данных:
    # логина, пароля, e-mail, телефона, имени, пола и даты рождения.
    return await _request("POST", "/api/users/register", json=payload)


async def login_user(email: str, password: str) -> httpx.Response:
    """Авторизация пользователя и получение токенов."""
    # Эндпоинт авторизации расположен по адресу ``/api/users/login``.
    return await _request(
        "POST",
        "/api/users/login",
        json={"email": email, "password": password},
    )


async def refresh_token(refresh_token: str) -> httpx.Response:
    """Обновление access-токена."""
    # Обновление токена производится по маршруту ``/api/users/refresh``.
    return await _request(
        "POST",
        "/api/users/refresh",
        json={"refresh_token": refresh_token},
    )


async def get_profile(token: str) -> httpx.Response:
    """Получение данных профиля пользователя."""
    # Данные профиля доступны по адресу ``/api/users/profile``.
    return await _request("GET", "/api/users/profile", token=token)


async def get_trainings(
    token: str, params: Optional[Dict[str, Any]] = None
) -> httpx.Response:
    """Получение списка тренировок пользователя."""
    # Список тренировок возвращается по маршруту ``/api/trainings``.
    return await _request("GET", "/api/trainings", token=token, params=params)