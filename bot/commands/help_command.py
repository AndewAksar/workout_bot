# bot/handlers/help_command.py
"""
Модуль: help_command.py
Описание: Модуль содержит обработчик команды /help.
Обработчик отправляет текстовое сообщение со списком доступных команд в виде ссылок.

Зависимости:
- telegram: Для взаимодействия с Telegram API.
- telegram.ext: Для работы с контекстом и обновлениями Telegram.
"""

from telegram import Update
from telegram.ext import ContextTypes
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup
)

from bot.utils.message_deletion import schedule_message_deletion
from bot.utils.logger import setup_logging


logger = setup_logging()

# Обработчик команды /help
async def help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id
    chat_id = update.message.chat_id
    message_id = update.message.message_id

    try:
        help_text = (
            "📋 <b>Доступные команды</b> — используйте их, если кнопки под"
            " сообщениями недоступны или вы предпочитаете текстовый ввод:\n\n"
            "• <code>/start</code> — перезапустить приветствие и увидеть главное"
            " меню. Полезно, если сообщения с кнопками были удалены.\n"
            "• <code>/settings</code> — открыть раздел настроек с личными"
            " данными, профилем и весом.\n"
            "• <code>/cancel</code> — прервать текущее действие (например, ввод"
            " веса или диалог с AI). Сообщение с командой исчезнет через пару"
            " секунд, это нормально.\n\n"
            "• <code>/register</code> — начать регистрацию на Gym-Stat прямо в"
            " чате. Бот шаг за шагом попросит логин, email и пароль.\n"
            "• <code>/login</code> — авторизоваться на Gym-Stat, чтобы загрузить"
            " профиль и историю веса.\n"
            "• <code>/delete_data</code> — полностью удалить сохранённые данные"
            " (Telegram + Gym-Stat токены).\n"
            "• <code>/contacts</code> — получить ссылку на владельца бота.\n\n"
            "ℹ️ <b>Совет:</b> почти все служебные сообщения бот удаляет через"
            " 5–15 секунд. Если не успели прочитать подсказку — введите"
            " команду ещё раз, она появится повторно."
        )

        await update.message.reply_text(help_text, parse_mode="HTML")

        # Планируем удаление сообщения с командой /help
        logger.info(f"Планируется удаление сообщения {message_id} в чате {chat_id}")
        schedule_message_deletion(
            context,
            [message_id],
            chat_id=chat_id,
            delay=5
        )

    except Exception as e:
        logger.error(f"Ошибка при обработке команды /help: {e}")
        await update.message.reply_text(
            "❌ Произошла ошибка. Попробуйте снова позже.",
            parse_mode="HTML"

        )
