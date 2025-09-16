# bot/handlers/profile_display.py
"""
Модуль: profile_display.py
Описание: Отображение профиля пользователя в зависимости от выбранного режима.
Зависимости:
- aiosqlite: Асинхронное локальное хранение данных.
- telegram, telegram.ext: Работа с Telegram API.
- bot.api.gym_stat_client: Запросы к Gym-Stat API.
- bot.utils.api_session: Управление access-токеном.
- bot.utils.db_utils: Получение режима пользователя.
- bot.keyboards.settings_menu: Клавиатура настроек.
"""

import aiosqlite
from telegram import Update
from telegram.ext import ContextTypes
import httpx
from datetime import date, datetime
import html

from bot.api.gym_stat_client import (
    get_profile as api_get_profile,
    get_weight_data as api_get_weight_data,
)
from bot.keyboards.settings_menu import get_settings_menu
from bot.utils.api_session import get_valid_access_token
from bot.utils.db_utils import get_user_mode
from bot.utils.message_deletion import schedule_message_deletion
from bot.utils.logger import setup_logging
from bot.utils.formatters import format_gender
from bot.config.settings import DB_PATH
from telegram.error import (
    BadRequest,
    TelegramError
)


logger = setup_logging()

async def show_profile(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отображает профиль пользователя."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    chat_id = query.message.chat_id
    logger.info("Пользователь %s запросил профиль", user_id)

    try:
        mode = await get_user_mode(user_id)
        if mode == "api":
            token = await get_valid_access_token(user_id)
            if not token:
                await query.message.edit_text(
                    "🔐 Требуется вход. Используйте /login.",
                    reply_markup=get_settings_menu(),
                )
                return
            try:
                resp = await api_get_profile(token)
            except httpx.HTTPError as e:
                logger.error("Ошибка запроса профиля для пользователя %s: %s", user_id, str(e))
                await query.message.edit_text(
                    "❌ Не удалось получить профиль. Попробуйте позже.",
                    reply_markup=get_settings_menu(),
                )
                return
            if resp.status_code != 200:
                logger.warning(
                    "Профиль не получен: %s %s", resp.status_code, resp.text
                )
                await query.message.edit_text(
                    "❌ Не удалось получить профиль. Попробуйте позже.",
                    reply_markup=get_settings_menu(),
                )
                return
            try:
                data = resp.json()
            except ValueError as e:
                logger.error("Некорректный ответ профиля для пользователя %s: %s", user_id, str(e))
                await query.message.edit_text(
                    "❌ Не удалось получить профиль. Попробуйте позже.",
                    reply_markup=get_settings_menu(),
                )
                return
            birth_date_raw = data.get("birthDate")
            birth_date = "Не указана"
            if birth_date_raw:
                try:
                    birth_dt = date.fromisoformat(birth_date_raw.split("T")[0])
                    today = date.today()
                    age = today.year - birth_dt.year - (
                            (today.month, today.day) < (birth_dt.month, birth_dt.day)
                    )
                    birth_date = f"{birth_dt.strftime('%d.%m.%Y')}({age})"
                except ValueError:
                    birth_date = birth_date_raw

            def esc(value: str | None, default: str = "Не указан") -> str:
                if value is None:
                    return default
                return html.escape(str(value))

            # goals = data.get("goals")
            # if isinstance(goals, list):
            #     goals = ", ".join(str(g) for g in goals)
            # goals = esc(goals, "Не указаны")

            last_weight_line = "Последнее взвешивание: <code>Не указано</code>\n"
            try:
                weight_resp = await api_get_weight_data(token)
                if weight_resp.status_code == 200:
                    weight_payload = weight_resp.json()
                    items = []
                    if isinstance(weight_payload, list):
                        items = weight_payload
                    elif isinstance(weight_payload, dict):
                        if isinstance(weight_payload.get("data"), list):
                            items = weight_payload["data"]
                        elif isinstance(weight_payload.get("results"), list):
                            items = weight_payload["results"]
                    if items:
                        items.sort(key=lambda x: x.get("date", ""), reverse=True)
                        latest = items[0]
                        w = latest.get("weight")
                        d_raw = latest.get("date")
                        if w is not None and d_raw:
                            try:
                                d_fmt = datetime.fromisoformat(d_raw.split("T")[0]).strftime("%d.%m.%Y")
                            except ValueError:
                                d_fmt = d_raw
                            last_weight_line = (
                                f"Вес: <code>{esc(w)}</code> кг от <code>{esc(d_fmt)}</code>\n"
                            )
            except Exception as e:
                logger.error(
                    "Ошибка получения данных взвешивания для пользователя %s: %s",
                    user_id,
                    str(e),
                )
            greeting = (
                f"<b>Ваш профиль на Gym-Stat:</b>\n"
                f"👤 Имя: <code>{esc(data.get('name'))}</code>\n"
                f"Дата рождения: <code>{html.escape(birth_date)}</code>\n"
                f"{last_weight_line}"
                f"Рост: <code>{esc(data.get('height'))}</code> см\n"
                f"Пол: <code>{format_gender(data.get('gender'))}</code>\n\n"
                f"📧 Email: <code>{esc(data.get('email'))}</code>\n"
                # f"🎯 Цели: <code>{goals}</code>"
            )
        else:
            async with aiosqlite.connect(DB_PATH) as db:
                async with db.execute(
                    "SELECT name, age, weight, height, gender, username FROM UserSettings WHERE user_id = ?",
                    (user_id,),
                ) as cursor:
                    profile = await cursor.fetchone()
            if profile:
                greeting = (
                    f"<b>Ваш профиль:</b>\n"
                    f"👤 Имя: <code>{profile[0] if profile[0] else 'Не указано'}</code>\n"
                    f"Возраст: <code>{profile[1] if profile[1] else 'Не указан'}</code>\n"
                    f"Вес: <code>{profile[2] if profile[2] else 'Не указан'}</code> кг\n"
                    f"Рост: <code>{profile[3] if profile[3] else 'Не указан'}</code> см\n"
                    f"Пол: <code>{profile[4] if profile[4] else 'Не указан'}</code>\n\n"
                    f"📧 Telegram: <code>@{profile[5] if profile[5] else 'Не указан'}</code>"
                )
            else:
                greeting = "⚠️ Профиль не найден. Пожалуйста, используйте /start для инициализации."
    except aiosqlite.Error as e:
        logger.error("Ошибка при отображении профиля для пользователя %s: %s", user_id, str(e))
        greeting = "❌ Произошла ошибка при отображении профиля."
    except Exception as e:
        logger.exception("Непредвиденная ошибка при отображении профиля для пользователя %s", user_id)
        greeting = "❌ Не удалось получить профиль. Попробуйте позже."
    try:
        await query.message.edit_text(
            greeting,
            parse_mode="HTML",
            reply_markup=get_settings_menu(),
        )
    except BadRequest as e:
        if "Message is not modified" in str(e):
            return
        sent_message = await query.message.reply_text(
            greeting,
            parse_mode="HTML",
            reply_markup=get_settings_menu(),
        )
        schedule_message_deletion(
            context, [sent_message.message_id], chat_id, delay=5
        )
    except TelegramError as e:
        logger.error(
            "Ошибка Telegram при отправке профиля пользователю %s: %s", user_id, str(e)
        )
        sent_message = await query.message.reply_text(
            "⚠️ Произошла ошибка. Попробуйте снова.",
            reply_markup=get_settings_menu(),
        )
        schedule_message_deletion(
            context, [sent_message.message_id], chat_id, delay=5
        )