# bot/handlers/start_command.py
"""
Модуль: start_command.py
Описание: Модуль содержит обработчик команды /start.

Зависимости:
- aiosqlite: Для асинхронной работы с базой данных SQLite.
- telegram: Для взаимодействия с Telegram API.
- telegram.ext: Для работы с контекстом и обновлениями Telegram.
- bot.config.settings: Для получения конфигурационных данных (WELCOME_MESSAGE).
- bot.keyboards.main_menu: Для генерации главного меню.
- bot.utils.message_deletion: Для планирования удаления сообщений.
"""

import asyncio
import os
import aiosqlite
from telegram import Update
from telegram.ext import ContextTypes

from bot.config.settings import WELCOME_MESSAGE, DB_PATH
from bot.keyboards.main_menu import get_main_menu
from bot.utils.logger import setup_logging
from bot.keyboards.mode_selection import (
    get_mode_selection_keyboard,
    get_api_auth_keyboard
)
from bot.utils.message_deletion import schedule_message_deletion
from bot.utils.api_session import get_valid_access_token


logger = setup_logging()

# Обработчик команды /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает команду /start."""
    # Извлечение данных пользователя из объекта Update
    user = update.message.from_user
    user_id = user.id
    username = user.username if user.username else "друг"
    first_name = user.first_name if user.first_name else ""

    mode = "local"

    try:
        logger.info(f"Подключение к базе данных: {DB_PATH}, файл существует: {os.path.exists(DB_PATH)}")
        from bot.database.db_init import init_db
        await asyncio.to_thread(init_db)
        profile = None
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT mode FROM users WHERE user_id = ?",
                (user_id,),
            ) as cursor:
                user_record = await cursor.fetchone()

            if not user_record:
                await db.execute(
                    "INSERT INTO users (user_id, telegram_username, mode) VALUES (?, ?, 'local')",
                    (user_id, username),
                )
                mode = "local"
            else:
                mode = user_record[0]
                await db.execute(
                    "INSERT OR IGNORE INTO UserSettings (user_id, username, name) VALUES (?, ?, ?)",
                    (user_id, username, first_name),
                )

            await db.execute(
                "UPDATE UserSettings SET username = ?, name = COALESCE(name, ?) WHERE user_id = ?",
                (username, first_name, user_id),
            )

            await db.execute(
                "UPDATE users SET telegram_username = ? WHERE user_id = ?",
                (username, user_id),
            )
            await db.commit()

            async with db.execute(
                    "SELECT name, age, weight, height, gender FROM UserSettings WHERE user_id = ?",
                    (user_id,),
            ) as cursor:
                profile = await cursor.fetchone()

        if not user_record:
            await update.message.reply_text(
                (
                    "💪 Добро пожаловать в бот для тренировок!\n"
                    "<b>Что такое режим?</b>\n"
                    "• <b>Telegram-версия</b> хранит данные только внутри бота."
                    " Подходит, если хотите вести заметки без регистрации.\n"
                    "• <b>Интеграция с Gym-Stat.ru</b> синхронизирует профиль"
                    " и вес с сайтом. Понадобится регистрация/вход.\n\n"
                    "<b>Как выбрать?</b> Нажмите кнопку под этим сообщением."
                    " После выбора бот покажет подсказки по дальнейшим шагам."
                    " Если сомневаетесь, начните с Telegram-версии — переключиться"
                    " можно в любой момент через «🔄 Сменить режим»."
                ),
                parse_mode="HTML",
                reply_markup=get_mode_selection_keyboard()
            )
            schedule_message_deletion(
                context,
                [update.message.message_id],
                chat_id=update.message.chat_id,
                delay=5)
            return

        # Формирование приветственного сообщения
        name = profile[0] if profile and profile[0] else username

        greeting = (
            f"<b>Привет, {name}! 👋</b>\n"
            f"Твой ID: <code>{user_id}</code>\n"
            f"{WELCOME_MESSAGE}"
        )

        greeting += (
            "\n\n<b>Как пользоваться главным меню:</b>\n"
            "• «🏋️‍♂️ Тренировки» — получи короткий чек-лист и добавь свои"
            " заметки о занятии.\n"
            "• «🗂️ Мои упражнения» — просмотр списка упражнений и групп упражнений (в режиме Gym-Stat.ru данные"
            " подтянутся с сайта).\n"
            "• «🔄 Сменить режим» — быстро переключайся между локальным и"
            " Gym-Stat.\n"
            "• «🤖 AI-консультант» — задай вопрос виртуальному тренеру.\n"
            "• «⚙️ Настройки» — открой управление личными данными и весом.\n\n"
            "<b>Подсказка:</b> если сообщение исчезло, открой /start повторно —"
            " бот прячёт команды, чтобы чат не захламлялся."
        )

        if mode == "api":
            token = await get_valid_access_token(user_id)
            if token:
                greeting += (
                    "\n🌐 Активен режим Gym-Stat. Авторизация сохранена."
                    " Чтобы увидеть серверные данные, загляни в «⚙️ Настройки» →"
                    " «👤 Показать профиль» или «⚖️ Данные взвешивания»."
                )
                await update.message.reply_text(
                    greeting,
                    parse_mode="HTML",
                    reply_markup=get_main_menu(mode=mode),
                )
            else:
                await update.message.reply_text(
                    (
                        "🌐 Режим Gym-Stat активен. Для продолжения требуется"
                        " авторизация.\n\n"
                        "Нажми «🔐 Войти», чтобы указать логин и пароль от"
                        " Gym-Stat, или «📝 Регистрация», если аккаунта ещё"
                        " нет. После успешного входа разделы профиля"
                        " и веса наполнятся данными автоматически."
                    ),
                    reply_markup=get_api_auth_keyboard(),
                )
        else:
            await update.message.reply_text(
                greeting,
                parse_mode="HTML",
                reply_markup=get_main_menu(mode=mode),
            )

        # Планируем удаление только сообщения с командой /start
        schedule_message_deletion(
            context,
            [update.message.message_id],
            chat_id=update.message.chat_id,
            delay=5
        )

    except aiosqlite.Error as e:
        logger.error(f"Ошибка базы данных для пользователя {user_id}: {e}")
        sent_message = await update.message.reply_text(
            "❌ Произошла ошибка при создании профиля. Попробуйте снова.",
            reply_markup=get_main_menu(mode=mode)
        )

        # Планируем удаление только сообщения с командой /start даже при ошибке
        schedule_message_deletion(
            context,
            [update.message.message_id],
            chat_id=update.message.chat_id,
            delay=5
        )

    except Exception as e:
        logger.error(f"Неожиданная ошибка для пользователя {user_id}: {e}")
        sent_message = await update.message.reply_text(
            "❌ Произошла непредвиденная ошибка. Попробуйте снова позже.",
            reply_markup=get_main_menu(mode=mode)
        )
        # Планируем удаление только сообщения с командой /start даже при ошибке
        schedule_message_deletion(
            context,
            [update.message.message_id],
            chat_id=update.message.chat_id,
            delay=5
        )

    finally:
        logger.info(f"Соединение с базой данных закрыто для пользователя {user_id}")

