# bot/utils/api_session.py
"""
Модуль: api_session.py
Описание: Управление access/refresh токенами Gym-Stat.ru.
Зависимости:
- datetime: Для проверки срока действия токена.
- bot.api.gym_stat_client: Для запросов обновления токена.
- bot.utils.encryption: Для шифрования и дешифрования токенов.
- bot.utils.db_utils: Для хранения токенов в базе.
"""

from datetime import datetime, timedelta
from typing import Optional

from bot.api.gym_stat_client import refresh_token as api_refresh
from bot.utils.encryption import (
    decrypt_token,
    encrypt_token
)
from bot.utils.db_utils import (
    get_api_tokens,
    save_api_tokens
)
from bot.utils.db_utils import (
    get_api_tokens,
    save_api_tokens,
    clear_api_tokens,
)
from bot.utils.logger import setup_logging


logger = setup_logging()

async def get_valid_access_token(user_id: int) -> Optional[str]:
    """Возвращает действующий access-токен, обновляя его при необходимости."""
    tokens = get_api_tokens(user_id)
    if not tokens:
        return None
    access_enc, refresh_enc, expires_at_str = tokens
    if not access_enc or not expires_at_str:
        clear_api_tokens(user_id)
        return None

    expires_at = datetime.fromisoformat(expires_at_str)

    if datetime.utcnow() > expires_at - timedelta(seconds=300):
        if not refresh_enc:
            logger.warning(
                "Отсутствует refresh_token; требуется повторная авторизация"
            )
            clear_api_tokens(user_id)
            return None
        refresh = decrypt_token(refresh_enc)
        if not refresh:
            logger.warning(
                "Некорректный refresh_token; требуется повторная авторизация"
            )
            clear_api_tokens(user_id)
            return None
        resp = await api_refresh(refresh)
        if resp.status_code != 200:
            logger.warning("Не удалось обновить токен: %s", resp.text)
            clear_api_tokens(user_id)
            return None
        data = resp.json()
        new_access = data.get("access_token")
        if not new_access:
            logger.error("Ответ API не содержит нового access_token: %s", data)
            clear_api_tokens(user_id)
            return None
        expires_in = data.get("expires_in", 3600)
        save_api_tokens(user_id, encrypt_token(new_access), refresh_enc, expires_in)
        return new_access
    access = decrypt_token(access_enc)
    if not access:
        clear_api_tokens(user_id)
        return None
    return access