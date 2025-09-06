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
- handlers.profile_display: Обработчик отображения профиля.
- handlers.misc_handlers: Обработчики для прочих функций (тренировки, настройки, меню).
- handlers.set_name, set_age, set_weight, set_height, set_gender: Обработчики ввода данных профиля.
- ai_assistant.ai_handler: Обработчики для AI-консультанта.
- database.db_init: Для инициализации базы данных.

Пример использования:
    >>> python bot/main.py
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

from bot.config.settings import TELEGRAM_TOKEN
from bot.utils.logger import setup_logging
from bot.commands.start_command import start
from bot.commands.help_command import help as help_command
from bot.commands.contact_command import contact
from bot.commands.settings_command import settings as settings_command
from bot.commands.cancel_command import cancel
from bot.handlers.profile_display import show_profile
from bot.handlers.misc_handlers import (
    start_training,
    show_trainings,
    show_settings,
    show_personal_data_menu,
    show_training_settings,
    return_to_main_menu
)
from bot.handlers.set_age import set_age
from bot.handlers.set_weight import set_weight
from bot.handlers.set_height import set_height
from bot.handlers.set_gender import set_gender
from bot.handlers.set_name import set_name
from bot.config.settings import (
    SET_NAME,
    SET_AGE,
    SET_WEIGHT,
    SET_HEIGHT,
    SET_GENDER,
    AI_CONSULTATION
)
from bot.ai_assistant.ai_handler import (
    start_ai_assistant,
    handle_ai_message,
    end_ai_consultation,
    ai_error_handler,
)
from bot.handlers.callbacks import (
    set_name_callback,
    set_age_callback,
    set_weight_callback,
    set_height_callback,
    set_gender_callback
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
    # Проверка наличия токена
    if not TELEGRAM_TOKEN:
        logger.critical("Переменная окружения TELEGRAM_TOKEN не задана. Завершение работы.")
        raise SystemExit(1)

    # Инициализация базы данных перед запуском бота
    init_db()

    # Создание объекта приложения Telegram-бота
    application = Application.builder().token(TELEGRAM_TOKEN).concurrent_updates(False).build()

    # Настройка ConversationHandler для интерактивного редактирования профиля и вызова AI-консультанта
    conv_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(show_profile, pattern='^show_profile$'),
            CallbackQueryHandler(start_training, pattern='^start_training$'),
            CallbackQueryHandler(show_trainings, pattern='^my_trainings$'),
            CallbackQueryHandler(start_ai_assistant, pattern='^my_ai_assistant$'),
            CallbackQueryHandler(start_ai_assistant, pattern='^start_ai_assistant$'),
            CallbackQueryHandler(show_settings, pattern='^settings$'),
            CallbackQueryHandler(show_personal_data_menu, pattern='^personal_data$'),
            CallbackQueryHandler(show_training_settings, pattern='^training_settings$'),
            CallbackQueryHandler(return_to_main_menu, pattern='^main_menu$'),
            CallbackQueryHandler(set_name_callback, pattern='^set_name$'),
            CallbackQueryHandler(set_age_callback, pattern='^set_age$'),
            CallbackQueryHandler(set_weight_callback, pattern='^set_weight$'),
            CallbackQueryHandler(set_height_callback, pattern='^set_height$'),
            CallbackQueryHandler(set_gender_callback, pattern='^set_gender$'),
        ],
        states={
            SET_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_name)],
            SET_AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_age)],
            SET_WEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_weight)],
            SET_HEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_height)],
            SET_GENDER: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_gender)],
            AI_CONSULTATION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_ai_message),
                CallbackQueryHandler(end_ai_consultation, pattern='^end_ai_consultation$'),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel)
        ],
        conversation_timeout=300,
        per_chat=True,  # Изоляция по чатам
        per_user=True   # Изоляция по пользователям
    )

    # Регистрация обработчиков команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("contacts", contact))
    application.add_handler(CommandHandler("settings", settings_command))

    # Регистрация обработчиков для кнопок из команды /help
    application.add_handler(CallbackQueryHandler(start, pattern='^start$'))
    application.add_handler(CallbackQueryHandler(contact, pattern='^contacts$'))

    # Регистрация обработчика для AI-консультации
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
