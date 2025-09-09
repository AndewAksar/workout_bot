# bot/handlers/mode_handlers.py
"""
Модуль: mode_handlers.py
Описание: Обработчики выбора и переключения режима работы бота.
Зависимости:
- sqlite3 - для работы с базой данных.
- httpx - для работы с HTTP-запросами.
- typing - для определения типов переменных.
- telegram - для работы с Telegram API.
- telegram.ext - для обработки событий Telegram.
- bot.config.settings - для получения настроек бота.
- bot.keyboards.main_menu - для создания клавиатуры главного меню.
- bot.keyboards.mode_selection - для создания клавиатуры выбора режима.
- bot.keyboards.settings_menu - для создания клавиатуры настроек.
- bot.utils.logger - для логирования событий.
"""

import sqlite3
from typing import Optional

import httpx
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from bot.config.settings import DB_PATH, GYMSTAT_API_URL
from bot.keyboards.main_menu import get_main_menu
from bot.keyboards.mode_selection import get_mode_selection_keyboard
from bot.keyboards.settings_menu import get_settings_menu
from bot.utils.logger import setup_logging


logger = setup_logging()

def _get_user_mode(user_id: int) -> Optional[str]:
    """Возвращает текущий режим пользователя."""
    conn = sqlite3.connect(DB_PATH)
    try:
        c = conn.cursor()
        c.execute("SELECT mode FROM users WHERE user_id = ?", (user_id,))
        row = c.fetchone()
        return row[0] if row else None
    finally:
        conn.close()

def _update_user_mode(user_id: int, mode: str) -> None:
    """Обновляет режим пользователя."""
    conn = sqlite3.connect(DB_PATH)
    try:
        c = conn.cursor()
        c.execute("UPDATE users SET mode = ? WHERE user_id = ?", (mode, user_id))
        conn.commit()
    finally:
        conn.close()

async def select_mode_local(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик выбора локального режима."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    _update_user_mode(user_id, 'local')
    logger.info(f"Пользователь {user_id} выбрал локальный режим")
    await query.message.edit_text(
        "Вы выбрали Telegram-версию. Данные будут храниться локально. Используйте /profile для настройки или /log для записи тренировок.",
        reply_markup=get_main_menu(),
    )
    await query.message.reply_text(
        "ℹ️ Бот сохраняет ваши данные (ID, режим, профиль) для работы. Удалить их можно через /delete_data.")

async def _api_available() -> bool:
    """Проверяет доступность API Gym-Stat."""
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{GYMSTAT_API_URL}/ping")
    except Exception as e:
        logger.exception("Ошибка при проверке API: %s", e)
        return False
    if resp.status_code >= 500:
        logger.warning(
            "Проверка API Gym-Stat вернула %s: %s", resp.status_code, resp.text
        )
        return False
    if resp.status_code != 200:
        logger.info(
            "Проверка API Gym-Stat вернула код %s: %s", resp.status_code, resp.text
        )
    return True

async def select_mode_api(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик выбора API режима."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if await _api_available():
        _update_user_mode(user_id, 'api')
        logger.info("Пользователь %s выбрал API режим", user_id)
        await query.message.edit_text(
            f"Вы выбрали интеграцию с Gym-Stat.ru. Используйте /register для регистрации или /login для входа.",
            reply_markup=get_main_menu(),
        )
    else:
        _update_user_mode(user_id, 'local')
        logger.warning(
            "Пользователь %s: API недоступно, остаёмся в локальном режиме", user_id
        )
        await query.message.edit_text(
            "⚠️ Сайт Gym-Stat.ru недоступен. Переключаемся на Telegram-версию.",
            reply_markup=get_main_menu(),
        )
    await query.message.reply_text(
        "ℹ️ Бот сохраняет ваши данные (ID, режим, профиль) для работы. Удалить их можно через /delete_data.")

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
    """Показывает подтверждение смены режима."""
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        user_id = query.from_user.id
        message = query.message
    else:
        user_id = update.message.from_user.id
        message = update.message

    current_mode = _get_user_mode(user_id) or 'local'
    target_mode = 'api' if current_mode == 'local' else 'local'
    text_mode = 'Интеграция с Gym-Stat.ru' if target_mode == 'api' else 'Telegram-версия'
    keyboard = [[
        InlineKeyboardButton("✅ Подтвердить", callback_data=f"confirm_switch_{target_mode}"),
        InlineKeyboardButton("❌ Отмена", callback_data="cancel_switch"),
    ]]
    markup = InlineKeyboardMarkup(keyboard)
    await message.reply_text(
        f"Вы хотите сменить режим на {text_mode}? Текущие данные останутся, но для интеграции потребуется регистрация.",
        reply_markup=markup,
    )

async def confirm_switch_mode(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Подтверждает смену режима."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    target_mode = query.data.replace('confirm_switch_', '')

    if target_mode == 'api' and not await _api_available():
        logger.warning(
            "Пользователь %s: попытка переключиться на API режим, но API недоступно",
            user_id,
        )
        await query.message.edit_text(
            "⚠️ Сайт Gym-Stat.ru недоступен. Остаёмся в Telegram-версии.",
            reply_markup=get_settings_menu(),
        )
        return

    _update_user_mode(user_id, target_mode)
    text_mode = 'Интеграция с Gym-Stat.ru' if target_mode == 'api' else 'Telegram-версия'
    await query.message.edit_text(
        f"Режим изменен на {text_mode}. Используйте /profile для настройки.",
        reply_markup=get_settings_menu(),
    )

async def cancel_switch(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отменяет смену режима."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    current_mode = _get_user_mode(user_id) or 'local'
    text_mode = 'Интеграция с Gym-Stat.ru' if current_mode == 'api' else 'Telegram-версия'
    await query.message.edit_text(
        f"⚙️ Настройки\nТекущий режим: {text_mode}\nДействие отменено.",
        reply_markup=get_settings_menu(),
    )