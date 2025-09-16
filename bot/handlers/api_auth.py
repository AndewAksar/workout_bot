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
import asyncio
from datetime import (
    date,
    datetime
)
import html
from telegram import Update
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
)

from bot.api.gym_stat_client import (
    register_user,
    login_user,
    get_profile,
    get_weight_data
)
from bot.utils.encryption import encrypt_token
from bot.utils.db_utils import save_api_tokens
from bot.utils.logger import setup_logging
from bot.keyboards.main_menu import get_main_menu
from bot.utils.formatters import format_gender
from bot.utils.message_deletion import schedule_message_deletion


logger = setup_logging()

# Состояния диалогов
# Для регистрации достаточно логина, почты и пароля
REG_LOGIN, REG_EMAIL, REG_PASSWORD, REG_CONFIRM = range(4)
LOGIN_LOGIN, LOGIN_PASSWORD = range(4, 6)


def _valid_email(email: str) -> bool:
    return re.match(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$", email) is not None


async def start_registration(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Начало диалога регистрации (как по команде, так и по кнопке)."""
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        message = query.message
    else:
        message = update.message
        schedule_message_deletion(
            context,
            [update.message.message_id],
            chat_id=update.message.chat_id,
            delay=5,
        )
    # Первым шагом запрашиваем логин, т.к. он обязателен при регистрации на сайте
    sent_message = await message.reply_text("👤 Введите логин:")
    schedule_message_deletion(
        context,
        [sent_message.message_id],
        chat_id=sent_message.chat_id,
        delay=30,
    )
    return REG_LOGIN


async def reg_login(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Получение логина пользователя."""
    login = update.message.text.strip()
    schedule_message_deletion(
        context,
        [update.message.message_id],
        chat_id=update.message.chat_id,
        delay=5,
    )
    if not login:
        sent_message = await update.message.reply_text("⚠️ Логин не может быть пустым. Введите снова:")
        schedule_message_deletion(
            context,
            [sent_message.message_id],
            chat_id=sent_message.chat_id,
            delay=30,
        )
        return REG_LOGIN
    context.user_data["reg_login"] = login  # сохраняем логин
    sent_message = await update.message.reply_text("✉️ Введите email:")
    schedule_message_deletion(
        context,
        [sent_message.message_id],
        chat_id=sent_message.chat_id,
        delay=5,
    )
    return REG_EMAIL


async def reg_email(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    email = update.message.text.strip()
    schedule_message_deletion(
        context,
        [update.message.message_id],
        chat_id=update.message.chat_id,
        delay=5,
    )
    if not _valid_email(email):
        sent_message = await update.message.reply_text("⚠️ Неверный формат email. Попробуйте снова:")
        schedule_message_deletion(
            context,
            [sent_message.message_id],
            chat_id=sent_message.chat_id,
            delay=5,
        )
        return REG_EMAIL
    context.user_data["reg_email"] = email
    sent_message = await update.message.reply_text("🔒 Введите пароль (мин. 8 символов):")
    schedule_message_deletion(
        context,
        [sent_message.message_id],
        chat_id=sent_message.chat_id,
        delay=5,
    )
    return REG_PASSWORD


async def reg_password(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    password = update.message.text.strip()
    schedule_message_deletion(
        context,
        [update.message.message_id],
        chat_id=update.message.chat_id,
        delay=5,
    )
    if len(password) < 8:
        sent_message = await update.message.reply_text("⚠️ Пароль слишком короткий. Введите заново:")
        schedule_message_deletion(
            context,
            [sent_message.message_id],
            chat_id=sent_message.chat_id,
            delay=5,
        )
        return REG_PASSWORD
    context.user_data["reg_password"] = password
    sent_message = await update.message.reply_text("🔁 Повторите пароль:")
    schedule_message_deletion(
        context,
        [sent_message.message_id],
        chat_id=sent_message.chat_id,
        delay=5,
    )
    return REG_CONFIRM


async def reg_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.text.strip() != context.user_data.get("reg_password"):
        schedule_message_deletion(
            context,
            [update.message.message_id],
            chat_id=update.message.chat_id,
            delay=5,
        )
        sent_message = await update.message.reply_text("⚠️ Пароли не совпадают. Введите пароль снова:")
        schedule_message_deletion(
            context,
            [sent_message.message_id],
            chat_id=sent_message.chat_id,
            delay=10,
        )
        return REG_PASSWORD
    schedule_message_deletion(
        context,
        [update.message.message_id],
        chat_id=update.message.chat_id,
        delay=5,
    )
    payload = {
        "login": context.user_data["reg_login"],
        "email": context.user_data["reg_email"],
        "password": context.user_data["reg_password"],
    }
    resp = await register_user(payload)
    if resp.status_code == 201:
        sent_message = await update.message.reply_text("✅ Регистрация успешна! Теперь выполните /login")
        schedule_message_deletion(
            context,
            [sent_message.message_id],
            chat_id=sent_message.chat_id,
            delay=5,
        )
    elif resp.status_code == 409:
        sent_message = await update.message.reply_text("⚠️ Email уже зарегистрирован. Используйте /login")
        schedule_message_deletion(
            context,
            [sent_message.message_id],
            chat_id=sent_message.chat_id,
            delay=5,
        )
    else:
        # Извлекаем текст ошибки из ответа API
        error_message = "❌ Ошибка регистрации. Попробуйте позже."
        try:
            error_data = resp.json()
            if isinstance(error_data.get("message"), list) and error_data["message"]:
                error_message = f"⚠️ Ошибка: {html.escape(error_data['message'][0])}"
            elif isinstance(error_data.get("message"), str):
                error_message = f"⚠️ Ошибка: {html.escape(error_data['message'])}"
            # Если нужно вернуться к вводу пароля для исправления
            if resp.status_code == 400:
                sent_message = await update.message.reply_text(
                    error_message + " Введите пароль заново:"
                )
                schedule_message_deletion(
                    context,
                    [sent_message.message_id],
                    chat_id=sent_message.chat_id,
                    delay=10,
                )
                return REG_PASSWORD
        except ValueError:
            logger.warning("Не удалось разобрать ответ API: %s %s", resp.status_code, resp.text)
        logger.warning("Registration failed: %s %s", resp.status_code, resp.text)
        sent_message = await update.message.reply_text(error_message)
        schedule_message_deletion(
            context,
            [sent_message.message_id],
            chat_id=sent_message.chat_id,
            delay=5,
        )
    return ConversationHandler.END


async def start_login(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Начало диалога авторизации (поддерживает кнопку и команду)."""
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        message = query.message
    else:
        message = update.message
        schedule_message_deletion(
            context,
            [update.message.message_id],
            chat_id=update.message.chat_id,
            delay=5,
        )
    context.user_data["login_attempts"] = 0
    sent_message = await message.reply_text("👤 Введите логин:")
    schedule_message_deletion(
        context,
        [sent_message.message_id],
        chat_id=sent_message.chat_id,
        delay=10,
    )
    return LOGIN_LOGIN


async def login_login(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    login = update.message.text.strip()
    schedule_message_deletion(
        context,
        [update.message.message_id],
        chat_id=update.message.chat_id,
        delay=5,
    )
    if not login:
        sent_message = await update.message.reply_text("⚠️ Логин не может быть пустым. Введите снова:")
        schedule_message_deletion(
            context,
            [sent_message.message_id],
            chat_id=sent_message.chat_id,
            delay=5,
        )
        return LOGIN_LOGIN
    context.user_data["login_login"] = login

    sent_message = await update.message.reply_text("🔒 Введите пароль:")
    schedule_message_deletion(
        context,
        [sent_message.message_id],
        chat_id=sent_message.chat_id,
        delay=10,
    )
    return LOGIN_PASSWORD


async def login_password(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["login_attempts"] += 1
    password = update.message.text.strip()
    login = context.user_data["login_login"]
    schedule_message_deletion(
        context,
        [update.message.message_id],
        chat_id=update.message.chat_id,
        delay=5,
    )
    resp = await login_user(login, password)
    if resp.status_code == 200:
        data = resp.json()
        access = data.get("access_token")
        refresh = data.get("refresh_token")
        if not access:
            logger.error("Сервер авторизации не вернул access_token: %s", data)
            sent_message = await update.message.reply_text(
                "❌ Авторизация не удалась: сервер не вернул access_token"
            )
            schedule_message_deletion(
                context,
                [sent_message.message_id],
                chat_id=sent_message.chat_id,
                delay=5,
            )
            return ConversationHandler.END
        if not refresh:
            logger.warning("Сервер не вернул refresh_token: %s", data)
        coroutines = [
            save_api_tokens(
                update.message.from_user.id,
                encrypt_token(access),
                encrypt_token(refresh) if refresh else None,
                data.get("expires_in", 3600),
            ),
            get_profile(access),
            get_weight_data(access),
        ]
        save_result, profile_result, weight_result = await asyncio.gather(
            *coroutines,
            return_exceptions=True,
        )

        if isinstance(save_result, Exception):
            logger.error(
                "Не удалось сохранить токены пользователя %s: %s",
                update.message.from_user.id,
                str(save_result),
            )

        profile_text = "<b>Профиль не найден.</b>"
        profile_response = None
        if isinstance(profile_result, Exception):
            logger.error(
                "Не удалось получить профиль пользователя %s: %s",
                update.message.from_user.id,
                str(profile_result),
            )
        else:
            profile_response = profile_result

        weight_response = None
        if isinstance(weight_result, Exception):
            logger.error(
                "Ошибка получения веса для пользователя %s: %s",
                update.message.from_user.id,
                str(weight_result),
            )
        else:
            weight_response = weight_result

        if profile_response and profile_response.status_code == 200:
            try:
                prof = profile_response.json()

                birth_raw = prof.get("birthDate")
                birth_fmt = "Не указана"
                if birth_raw:
                    try:
                        bd = date.fromisoformat(birth_raw.split("T")[0])
                        today = date.today()
                        age = today.year - bd.year - (
                            (today.month, today.day) < (bd.month, bd.day)
                        )
                        birth_fmt = f"{bd.strftime('%d.%m.%Y')}({age})"
                    except ValueError:
                        birth_fmt = birth_raw

                def esc(val, default="Не указан"):
                    return html.escape(str(val)) if val is not None else default

                weight_line = "Вес: <code>Не указан</code>\n"
                if weight_response and weight_response.status_code == 200:
                    try:
                        payload = weight_response.json()
                        items = []
                        if isinstance(payload, list):
                            items = payload
                        elif isinstance(payload, dict):
                            if isinstance(payload.get("data"), list):
                                items = payload["data"]
                            elif isinstance(payload.get("results"), list):
                                items = payload["results"]
                        if items:
                            items.sort(key=lambda x: x.get("date", ""), reverse=True)
                            latest = items[0]
                            w = latest.get("weight")
                            d_raw = latest.get("date")
                            if w is not None and d_raw:
                                try:
                                    d_fmt = datetime.fromisoformat(
                                        d_raw.split("T")[0]
                                    ).strftime("%d.%m.%Y")
                                except ValueError:
                                    d_fmt = d_raw
                                weight_line = (
                                    f"Вес: <code>{esc(w)}</code> кг от <code>{esc(d_fmt)}</code>\n"
                                )
                    except Exception as e:
                        logger.error(
                            "Ошибка получения веса для пользователя %s: %s",
                            update.message.from_user.id,
                            str(e),
                        )

                profile_text = (
                    f"<b>Привет, {esc(prof.get('name')) or 'пользователь'}! 👋</b>\n"
                    f"👤 Имя: <code>{esc(prof.get('name'))}</code>\n"
                    f"Дата рождения: <code>{html.escape(birth_fmt)}</code>\n"
                    f"{weight_line}"
                    f"Рост: <code>{esc(prof.get('height'))}</code> см\n"
                    f"Пол: <code>{format_gender(prof.get('gender'))}</code>"
                )
            except Exception as e:
                logger.error(
                    "Не удалось получить профиль пользователя %s: %s",
                    update.message.from_user.id,
                    str(e),
                )

        await update.message.reply_text(
            profile_text,
            parse_mode="HTML",
            reply_markup=get_main_menu(),
        )

        return ConversationHandler.END
    if resp.status_code == 401 and context.user_data["login_attempts"] < 3:
        sent_message = await update.message.reply_text("❌ Неверные данные. Попробуйте снова:")
        schedule_message_deletion(
            context,
            [sent_message.message_id],
            chat_id=sent_message.chat_id,
            delay=5,
        )
        return LOGIN_PASSWORD
    if resp.status_code == 429:
        sent_message = await update.message.reply_text("⏳ Слишком много попыток. Попробуйте позже")
        schedule_message_deletion(
            context,
            [sent_message.message_id],
            chat_id=sent_message.chat_id,
            delay=5,
        )
    else:
        sent_message = await update.message.reply_text("❌ Авторизация не удалась")
        schedule_message_deletion(
            context,
            [sent_message.message_id],
            chat_id=sent_message.chat_id,
            delay=5,
        )
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    schedule_message_deletion(
        context,
        [update.message.message_id],
        chat_id=update.message.chat_id,
        delay=5,
    )
    sent_message = await update.message.reply_text("⚠️ Операция отменена!")
    schedule_message_deletion(
        context,
        [sent_message.message_id],
        chat_id=sent_message.chat_id,
        delay=5,
    )
    return ConversationHandler.END