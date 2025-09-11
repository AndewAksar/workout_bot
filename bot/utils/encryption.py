# bot/utils/encryption.py
"""
Модуль: encryption.py
Описание: Утилиты для шифрования и дешифрования токенов Gym-Stat.ru.
Зависимости:
- cryptography.fernet: Для симметричного шифрования.
- bot.config.settings: Для получения ключа шифрования.
"""

from typing import Optional
from cryptography.fernet import Fernet

from bot.utils.logger import setup_logging
from bot.config.settings import ENCRYPT_KEY


logger = setup_logging()
fernet = Fernet(ENCRYPT_KEY)

def encrypt_token(token: Optional[str]) -> Optional[str]:
    """Шифрует строку токена.
    Если ``token`` имеет значение ``None`` или пустую строку, возвращает ``None``.
    Это позволяет безопасно обрабатывать случаи, когда API не вернул токен.
    """
    if not token:
        logger.warning("encrypt_token получил пустое значение токена")
        return None
    return fernet.encrypt(token.encode()).decode()

def decrypt_token(token_encrypted: str) -> str:
    """Расшифровывает строку токена.
    Если ``token_encrypted`` пустой или ``None``, возвращает ``None``.
    """
    if not token_encrypted:
        logger.warning("decrypt_token получил пустое значение токена")
        return None
    return fernet.decrypt(token_encrypted.encode()).decode()