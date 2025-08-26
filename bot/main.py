# bot/main.py
"""
Модуль: main.py
Описание: Основной модуль для запуска Telegram-бота, который предоставляет функционал для управления пользовательскими профилями,
включая команды для старта, получения справки и контактов, а также интерактивное редактирование профиля через ConversationHandler.
Бот использует библиотеку python-telegram-bot для обработки входящих сообщений и callback-запросов.

Зависимости:
- telegram: Для взаимодействия с Telegram API.
- telegram.ext: Для построения структуры бота (Application, Handlers).
- config.settings: Для получения конфигурационных данных (TELEGRAM_TOKEN).
- utils.logger: Для настройки логирования.
- handlers.commands: Обработчики команд /start, /help, /contacts.
- handlers.callbacks: Обработчики callback-запросов и состояний ConversationHandler.
- database.db_init: Для инициализации базы данных.

Пример использования:
    >>> python bot/main.py

Автор: Aksarin A.
Дата создания: 19/08/2025
"""

import sys
import os

# Добавление корневой директории проекта в sys.path для корректного импорта модулей и запуск скрипта
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ConversationHandler,
    MessageHandler,
    filters
)

from config.settings import TELEGRAM_TOKEN
from utils.logger import setup_logging
from bot.commands.start_command import start
from bot.commands.help_command import help
from bot.commands.contact_command import contact
from bot.commands.settings_command import settings
from bot.commands.cancel_command import cancel

from handlers.callbacks import button_callback
from handlers.set_age import set_age
from handlers.set_weight import set_weight
from handlers.set_height import set_height
from handlers.set_gender import set_gender
from bot.handlers.set_name import set_name
from handlers.callbacks import (
    SET_NAME,
    SET_AGE,
    SET_WEIGHT,
    SET_HEIGHT,
    SET_GENDER
)
from bot.ai_assistant.ai_handler import (
    start_ai_assistant,
    handle_ai_message,
    end_ai_consultation,
    ai_error_handler,
    AI_CONSULTATION
)
from bot.database.db_init import init_db


# Инициализация логгера для записи событий и ошибок
logger = setup_logging()

def main() -> None:
    """
        Основная функция для запуска Telegram-бота.
        Описание:
            Инициализирует базу данных, создает объект приложения Telegram-бота,
            настраивает обработчики команд и callback-запросов, а также запускает
            процесс polling для обработки входящих обновлений.
        Аргументы: Нет
        Возвращаемое значение: None
        Исключения:
            - RuntimeError: Если TELEGRAM_TOKEN не задан или недоступен.
            - Exception: Общие ошибки, связанные с инициализацией базы данных или запуском бота.
        Пример использования:
        >>> main()
        [Бот запускается, начинает обработку входящих сообщений]
    """
    # Инициализация базы данных перед запуском бота
    init_db()

    # Создание объекта приложения Telegram-бота
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # Настройка ConversationHandler для интерактивного редактирования профиля
    conv_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(
                button_callback
            )
        ],
        states={
            SET_NAME: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    set_name
                )
            ],
            SET_AGE: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    set_age
                )
            ],
            SET_WEIGHT: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    set_weight
                )
            ],
            SET_HEIGHT: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    set_height
                )
            ],
            SET_GENDER: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    set_gender
                )
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel)
        ],
        conversation_timeout=300
    )

    ai_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_ai_assistant, pattern='^start_ai_assistant$')],
        states={
            AI_CONSULTATION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_ai_message),
                CallbackQueryHandler(end_ai_consultation, pattern='^end_ai_consultation$')
            ],
        },
        fallbacks=[CommandHandler('cancel', cancel)],  # Если есть команда /cancel
        per_chat=True,
        per_user=True
    )

    # Регистрация обработчиков команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help))
    application.add_handler(CommandHandler("contacts", contact))
    application.add_handler(CommandHandler("settings", settings))
    # application.add_handler(CallbackQueryHandler(button_callback))

    # Регистрация обработчика для AI-консультации
    application.add_handler(ai_conv_handler)
    application.add_error_handler(ai_error_handler)

    # Регистрация обработчика ConversationHandler для обработки состояний
    application.add_handler(conv_handler)

    # Логирование успешного запуска бота
    logger.info("Бот запущен")

    # Запуск процесса polling для обработки всех типов обновлений
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    # Точка входа в приложение. Проверяет, что скрипт запущен напрямую, и вызывает основную функцию main().
    main()