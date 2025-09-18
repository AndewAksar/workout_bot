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


# Создаём глобальный асинхронный клиент HTTP
_client = httpx.AsyncClient()


async def _request(method: str, endpoint: str, token: str | None = None,
                   json: dict | None = None, params: dict | None = None) -> httpx.Response:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    url = f"{GYMSTAT_API_URL.rstrip('/')}/{endpoint.lstrip('/')}"
    resp = await _client.request(method, url, headers=headers, json=json, params=params)
    if resp.status_code >= 400:
        logger.warning("%s %s -> %s: %s", method, url, resp.status_code, resp.text)
    return resp


async def register_user(payload: Dict[str, Any]) -> httpx.Response:
    """Регистрация нового пользователя.
    Обязательные поля: ``login``, ``email`` и ``password``. Остальные можно
    передавать по необходимости.
    """
    return await _request("POST", "/api/users/register", json=payload)


async def login_user(login: str, password: str) -> httpx.Response:
    """Авторизация пользователя и получение токенов."""
    # Эндпоинт авторизации расположен по адресу ``/api/auth/login``.
    return await _request(
        "POST",
        "/api/auth/login",
        json={"login": login, "password": password},
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
    # Данные профиля доступны по адресу ``/api/users/me``.
    return await _request("GET", "/api/users/me", token=token)


async def update_profile(token: str, payload: Dict[str, Any]) -> httpx.Response:
    """Обновление данных профиля пользователя.
    Отправляет PATCH-запрос на эндпоинт ``/api/users/me`` с указанными данными.
    Args:
        token: Текущий access-токен пользователя.
        payload: Словарь с полями профиля для обновления.
    Returns:
        httpx.Response: Ответ сервера Gym-Stat.
    """
    return await _request("PATCH", "/api/users/me", token=token, json=payload)


async def get_trainings(
    token: str, params: Optional[Dict[str, Any]] = None
) -> httpx.Response:
    """Получение списка тренировок пользователя."""
    # Список тренировок возвращается по маршруту ``/api/trainings``.
    return await _request("GET", "/api/trainings", token=token, params=params)


async def get_weight_data(
    token: str, params: Optional[Dict[str, Any]] = None
) -> httpx.Response:
    """Получение истории взвешиваний пользователя."""
    # История взвешиваний доступна по адресу ``/api/weight-data``.
    return await _request("GET", "/api/weight-data", token=token, params=params)


async def create_weight_data(token: str, payload: Dict[str, Any]) -> httpx.Response:
    """Создание новой записи о взвешивании пользователя."""
    # Новое взвешивание создаётся по маршруту ``/api/weight-data``.
    return await _request("POST", "/api/weight-data", token=token, json=payload)