# bot/utils/encryption.py
"""
Модуль: encryption.py
Описание: Утилиты для шифрования и дешифрования токенов Gym-Stat.ru.
Зависимости:
- cryptography.fernet: Для симметричного шифрования.
- bot.config.settings: Для получения ключа шифрования.
"""

from cryptography.fernet import Fernet

from bot.config.settings import ENCRYPT_KEY


fernet = Fernet(ENCRYPT_KEY)

def encrypt_token(token: str) -> str:
    """Шифрует строку токена."""
    return fernet.encrypt(token.encode()).decode()

def decrypt_token(token_encrypted: str) -> str:
    """Расшифровывает строку токена."""
    return fernet.decrypt(token_encrypted.encode()).decode()