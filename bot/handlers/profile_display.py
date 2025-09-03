# bot/handlers/profile_display.py
"""
Модуль: profile_display.py
Описание: Модуль содержит функции для отображения профиля пользователя Telegram-бота.
Зависимости:
- sqlite3: Для работы с базой данных SQLite.
- telegram: Для взаимодействия с Telegram API.
- telegram.ext: Для работы с контекстом.
- bot.keyboards.settings_menu: Для получения клавиатуры настроек.
- bot.utils.logger: Для настройки логирования.
- bot.config.settings: Для доступа к константам конфигурации.
"""

import sqlite3
from telegram import Update
from telegram.ext import ContextTypes

from bot.keyboards.settings_menu import get_settings_menu
from bot.utils.message_deletion import schedule_message_deletion
from bot.utils.logger import setup_logging
from bot.config.settings import DB_PATH
from telegram.error import BadRequest


logger = setup_logging()

async def show_profile(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Отображает профиль пользователя на основе данных из базы данных.
    Аргументы:
        update (telegram.Update): Объект обновления, содержащий информацию о callback-запросе.
        context (telegram.ext.ContextTypes.DEFAULT_TYPE): Контекст выполнения команды.
    Исключения:
        sqlite3.Error: Если возникают ошибки при работе с базой данных.
    """
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    chat_id = query.message.chat_id
    logger.info(f"Пользователь {user_id} запросил отображение профиля")

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    try:
        c.execute("SELECT name, age, weight, height, gender, username "
                  "FROM UserSettings "
                  "WHERE user_id = ?",
                  (user_id,))
        profile = c.fetchone()
        logger.info(f"Профиль для user_id {user_id}: {profile}")
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

        # Попытка редактирования текущего сообщения
        try:
            await query.message.edit_text(
                greeting,
                parse_mode="HTML",
                reply_markup=get_settings_menu()
            )
            logger.info(f"Сообщение профиля для пользователя {user_id} успешно обновлено")
        except BadRequest as e:
            if "Message is not modified" in str(e):
                logger.debug(f"Сообщение профиля для пользователя {user_id} не обновлено: данные не изменились")
                return  # Пропускаем отправку нового сообщения
            else:
                logger.warning(
                    f"Не удалось отредактировать сообщение для пользователя {user_id}: {str(e)}. "
                    f"Отправка нового сообщения."
                )
                sent_message = await query.message.reply_text(
                    greeting,
                    parse_mode="HTML",
                    reply_markup=get_settings_menu()
                )
                await schedule_message_deletion(context, [sent_message.message_id], chat_id, delay=5)
    except sqlite3.Error as e:
        logger.error(f"Ошибка при отображении профиля для пользователя {user_id}: {str(e)}")
        try:
            await query.message.edit_text(
                "❌ Произошла ошибка при отображении профиля.",
                reply_markup=get_settings_menu()
            )
            logger.info(f"Сообщение об ошибке для пользователя {user_id} успешно обновлено")
        except BadRequest as e:
            if "Message is not modified" in str(e):
                logger.debug(f"Сообщение об ошибке для пользователя {user_id} не обновлено: данные не изменились")
                return
            else:
                logger.warning(
                    f"Не удалось отредактировать сообщение об ошибке для пользователя {user_id}: {str(e)}. "
                    f"Отправка нового сообщения."
                )
                sent_message = await query.message.reply_text(
                    "❌ Произошла ошибка при отображении профиля.",
                    reply_markup=get_settings_menu()
                )
                # Планируем удаление сообщения об ошибке через 5 секунд
                await schedule_message_deletion(context, [sent_message.message_id], chat_id, delay=5)
    finally:
        conn.close()