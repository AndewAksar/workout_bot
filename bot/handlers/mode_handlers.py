# bot/handlers/mode_handlers.py
"""
Модуль: mode_handlers.py
Описание: Обработчики выбора и переключения режима работы бота.
Зависимости:
- aiosqlite - для асинхронной работы с базой данных.
- httpx - для работы с HTTP-запросами.
- typing - для определения типов переменных.
- telegram - для работы с Telegram API.
- telegram.ext - для обработки событий Telegram.
- bot.config.settings - для получения настроек бота.
- bot.keyboards.main_menu - для создания клавиатуры главного меню.
- bot.keyboards.settings_menu - для создания клавиатуры настроек.
- bot.keyboards.mode_selection - для создания клавиатур выбора режима и авторизации.
- bot.utils.logger - для логирования событий.
"""

import aiosqlite
from typing import Optional
import httpx
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from bot.config.settings import (
    DB_PATH,
    GYMSTAT_API_URL
)
from bot.keyboards.main_menu import get_main_menu
from bot.keyboards.settings_menu import get_settings_menu
from bot.keyboards.mode_selection import (
    get_mode_selection_keyboard,
    get_api_auth_keyboard,
)
from bot.utils.logger import setup_logging


logger = setup_logging()

async def _get_user_mode(user_id: int) -> Optional[str]:
    """Возвращает текущий режим пользователя."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT mode FROM users WHERE user_id = ?",
            (user_id,),
        ) as cursor:
            row = await cursor.fetchone()
    return row[0] if row else None


async def _update_user_mode(user_id: int, mode: str) -> None:
    """Обновляет режим пользователя."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET mode = ? WHERE user_id = ?",
            (mode, user_id),
        )
        await db.commit()


async def select_mode_local(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает подтверждение переключения на Telegram-версию."""
    query = update.callback_query
    await query.answer()

    keyboard = [
        [
            InlineKeyboardButton("✅ Подтвердить", callback_data="confirm_switch_local"),
            InlineKeyboardButton("❌ Отмена", callback_data="cancel_switch"),
        ]
    ]
    await query.message.edit_text(
        "Переключиться на Telegram-версию? Все данные будут храниться локально.",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def _api_available() -> bool:
    """Проверяет доступность API Gym-Stat."""
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(GYMSTAT_API_URL)
    except Exception as e:
        logger.exception("Ошибка при проверке API: %s", e)
        return False
    if resp.status_code >= 500:
        logger.warning(
            "Проверка API Gym-Stat вернула %s: %s", resp.status_code, resp.text
        )
        return False
    return True


async def select_mode_api(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает подтверждение переключения на режим API."""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    keyboard = [
        [
            InlineKeyboardButton("✅ Подтвердить", callback_data="confirm_switch_api"),
            InlineKeyboardButton("❌ Отмена", callback_data="cancel_switch"),
        ]
    ]
    await query.message.edit_text(
        "Переключиться на интеграцию с Gym-Stat.ru? Для работы потребуется авторизация.",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def show_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /help."""
    query = update.callback_query
    await query.answer()
    text = (
        "📱 Telegram-версия: Данные хранятся только в боте. Подходит для простого использования.\n"
        "🌐 Интеграция с Gym-Stat.ru: Синхронизация с сайтом, доступ к веб-кабинету. Требуется регистрация.\n"
        "Выберите режим или используйте /settings для смены."
    )
    await query.message.edit_text(text, reply_markup=get_mode_selection_keyboard())


async def switch_mode_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Выводит клавиатуру выбора режима."""
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        await query.message.edit_text(
            "Выберите режим работы:", reply_markup=get_mode_selection_keyboard()
        )
    else:
        await update.message.reply_text(
            "Выберите режим работы:", reply_markup=get_mode_selection_keyboard()
        )

async def confirm_switch_mode(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Переключает режим после подтверждения."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    target_mode = query.data.replace("confirm_switch_", "")

    if target_mode == "api":
        if not await _api_available():
            logger.warning(
                "Пользователь %s: API недоступно, остаёмся в локальном режиме", user_id
            )
            await _update_user_mode(user_id, "local")
            await query.message.edit_text(
                "⚠️ Сайт Gym-Stat.ru недоступен. Остаёмся в Telegram-версии.",
                reply_markup=get_main_menu(),
            )
            return
        await _update_user_mode(user_id, "api")
        await query.message.edit_text(
            "Режим изменен на интеграцию с Gym-Stat.ru. Выберите действие:",
            reply_markup=get_api_auth_keyboard(),
        )
    else:
        await _update_user_mode(user_id, "local")
        await query.message.edit_text(
            "Режим изменен на Telegram-версию.", reply_markup=get_main_menu()
        )


async def cancel_switch(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Возвращает пользователя к выбору режима."""
    query = update.callback_query
    await query.answer()
    await query.message.edit_text(
        "Выбор режима отменён. Выберите режим:",
        reply_markup=get_mode_selection_keyboard(),
    )