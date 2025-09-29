# bot/handlers/settings_command.py
"""Обработчик команды /settings."""

import aiosqlite
from telegram import Update
from telegram.ext import ContextTypes

from bot.keyboards.settings_menu import get_settings_menu
from bot.utils.message_deletion import schedule_message_deletion
from bot.utils.logger import setup_logging
from bot.config.settings import DB_PATH


logger = setup_logging()

# Обработчик команды /settings
async def settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id
    chat_id = update.message.chat_id
    message_id = update.message.message_id

    try:
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                    "SELECT mode FROM users WHERE user_id = ?",
                    (user_id,),
            ) as cursor:
                row = await cursor.fetchone()
        mode = row[0] if row else 'local'
        mode_text = 'Интеграция с Gym-Stat.ru' if mode == 'api' else 'Telegram-версия'

        api_hint = ""
        if mode == 'api':
            api_hint = (
                "• «📏 Мои параметры» — посмотреть последние замеры тела из Gym-Stat.\n"
                "• «📊 Статистика» — перейти к диаграммам по упражнениям,"
                " тренировкам и весу на сайте Gym-Stat.\n"
            )

        await update.message.reply_text(
            (
                "⚙️ <b>Настройки</b>\n"
                f"Текущий режим: <code>{mode_text}</code>\n\n"
                "• «📋 Личные данные» — поменять имя, возраст, вес, рост и пол."
                " После нажатия выберите нужный пункт и отправьте значение"
                " текстом.\n"
                "• «👤 Показать профиль» — посмотреть текущие данные. Если"
                " что-то пусто, заполните раздел «Личные данные».\n"
                f"{api_hint}"
                "• «⚖️ Данные взвешивания» — история веса (активна после входа"
                " в Gym-Stat). Ссылки откроются на сайте Gym-Stat.\n"
                "• «🔙 Назад в главное меню» — вернуться к основным кнопкам.\n\n"
                "<i>Совет: если бот попросил авторизоваться, выполните /login"
                " или используйте кнопку «Войти» в режиме Gym-Stat.</i>"
            ),
            parse_mode="HTML",
            reply_markup=get_settings_menu(mode=mode)
        )

        # Планируем удаление только сообщения с командой /settings
        logger.info(f"Планируется удаление сообщения {message_id} в чате {chat_id}")
        schedule_message_deletion(
            context,
            [message_id],
            chat_id=chat_id,
            delay=5
        )

    except Exception as e:
        logger.error(f"Ошибка при обработке команды /settings: {e}")
        await update.message.reply_text(
            "❌ Произошла ошибка. Попробуйте снова позже.",
            parse_mode="HTML"
        )