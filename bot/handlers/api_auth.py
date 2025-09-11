# bot/handlers/api_auth.py
"""
Модуль: api_auth.py
Описание: Диалоги регистрации и авторизации через API Gym-Stat.ru.
Зависимости:
- httpx: Для отправки HTTP-запросов.
- telegram и telegram.ext: Для взаимодействия с Telegram.
- bot.api.gym_stat_client: Клиент Gym-Stat.
- bot.utils.encryption: Для шифрования токенов.
- bot.utils.db_utils: Для сохранения токенов и определения режима.
"""

import re
from typing import Dict

from telegram import Update
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
)

from bot.api.gym_stat_client import register_user, login_user
from bot.utils.encryption import encrypt_token
from bot.utils.db_utils import save_api_tokens
from bot.utils.logger import setup_logging

logger = setup_logging()

# Состояния диалогов
# Для регистрации достаточно логина, почты и пароля
REG_LOGIN, REG_EMAIL, REG_PASSWORD, REG_CONFIRM = range(4)
LOGIN_LOGIN, LOGIN_PASSWORD = range(4, 6)

def _valid_email(email: str) -> bool:
    return re.match(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$", email) is not None


async def start_registration(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # Первым шагом запрашиваем логин, т.к. он обязателен при регистрации на сайте
    await update.message.reply_text("👤 Введите логин:")
    return REG_LOGIN


async def reg_login(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Получение логина пользователя."""
    login = update.message.text.strip()
    if not login:
        await update.message.reply_text("⚠️ Логин не может быть пустым. Введите снова:")
        return REG_LOGIN
    context.user_data["reg_login"] = login  # сохраняем логин
    await update.message.reply_text("✉️ Введите email:")
    return REG_EMAIL


async def reg_email(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    email = update.message.text.strip()
    if not _valid_email(email):
        await update.message.reply_text("⚠️ Неверный формат email. Попробуйте снова:")
        return REG_EMAIL
    context.user_data["reg_email"] = email
    await update.message.reply_text("🔒 Введите пароль (мин. 8 символов):")
    return REG_PASSWORD


async def reg_password(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    password = update.message.text.strip()
    if len(password) < 8:
        await update.message.reply_text("⚠️ Пароль слишком короткий. Введите заново:")
        return REG_PASSWORD
    context.user_data["reg_password"] = password
    await update.message.reply_text("🔁 Повторите пароль:")
    return REG_CONFIRM


async def reg_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.text.strip() != context.user_data.get("reg_password"):
        await update.message.reply_text("⚠️ Пароли не совпадают. Введите пароль снова:")
        return REG_PASSWORD
    payload = {
        "login": context.user_data["reg_login"],
        "email": context.user_data["reg_email"],
        "password": context.user_data["reg_password"],
    }
    resp = await register_user(payload)
    if resp.status_code == 201:
        await update.message.reply_text("✅ Регистрация успешна! Теперь выполните /login")
    elif resp.status_code == 409:
        await update.message.reply_text("⚠️ Email уже зарегистрирован. Используйте /login")
    else:
        logger.warning("Registration failed: %s %s", resp.status_code, resp.text)
        await update.message.reply_text("❌ Ошибка регистрации. Попробуйте позже")
    return ConversationHandler.END


async def start_login(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["login_attempts"] = 0
    await update.message.reply_text("👤 Введите логин:")
    return LOGIN_LOGIN


async def login_login(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    login = update.message.text.strip()
    if not login:
        await update.message.reply_text("⚠️ Логин не может быть пустым. Введите снова:")
        return LOGIN_LOGIN
    context.user_data["login_login"] = login
    await update.message.reply_text("🔒 Введите пароль:")
    return LOGIN_PASSWORD


async def login_password(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["login_attempts"] += 1
    password = update.message.text.strip()
    login = context.user_data["login_login"]
    resp = await login_user(login, password)
    if resp.status_code == 200:
        data = resp.json()
        access = data.get("access_token")
        refresh = data.get("refresh_token")
        if not access:
            logger.error("Сервер авторизации не вернул access_token: %s", data)
            await update.message.reply_text(
                "❌ Авторизация не удалась: сервер не вернул access_token"
            )
            return ConversationHandler.END
        if not refresh:
            logger.warning("Сервер не вернул refresh_token: %s", data)
        save_api_tokens(
            update.message.from_user.id,
            encrypt_token(access),
            encrypt_token(refresh) if refresh else None,
            data.get("expires_in", 3600),
        )
        await update.message.reply_text("✅ Вы вошли! Используйте /profile или /trainings")
        return ConversationHandler.END
    if resp.status_code == 401 and context.user_data["login_attempts"] < 3:
        await update.message.reply_text("❌ Неверные данные. Попробуйте снова:")
        return LOGIN_PASSWORD
    if resp.status_code == 429:
        await update.message.reply_text("⏳ Слишком много попыток. Попробуйте позже")
    else:
        await update.message.reply_text("❌ Авторизация не удалась")
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Операция отменена")
    return ConversationHandler.END