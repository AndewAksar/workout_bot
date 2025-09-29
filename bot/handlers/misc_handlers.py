# bot/handlers/misc_handlers.py
"""
Модуль: misc_handlers.py
Описание: Модуль содержит обработчики для прочих функций Telegram-бота, таких как начало тренировки,
отображение тренировок и переход в меню настроек.
Зависимости:
- telegram: Для взаимодействия с Telegram API.
- telegram.ext: Для работы с контекстом и ConversationHandler.
- bot.keyboards.main_menu: Для получения клавиатуры главного меню.
- bot.keyboards.settings_menu: Для получения клавиатуры настроек.
- bot.keyboards.personal_data_menu: Для получения клавиатуры персональных данных.
- bot.keyboards.training_settings_menu: Для получения клавиатуры настроек тренировок.
- bot.utils.logger: Для настройки логирования.
"""

import aiosqlite
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from bot.keyboards.main_menu import get_main_menu
from bot.keyboards.settings_menu import get_settings_menu
from bot.keyboards.personal_data_menu import get_personal_data_menu
from bot.keyboards.training_settings_menu import get_training_settings_menu
from bot.keyboards.stats_menu import get_stats_menu
from bot.utils.db_utils import get_user_mode
from bot.utils.logger import setup_logging
from bot.config.settings import DB_PATH


logger = setup_logging()

async def start_training(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает начало тренировки."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    logger.info(f"Пользователь {user_id} начал тренировку")

    mode = await get_user_mode(user_id)

    await query.message.edit_text(
        (
            "🏋️‍♂️ <b>Тренировка начата!</b>\n"
            "1. Запиши в чате основные упражнения, подходы и веса — так ты"
            " оставишь заметку для себя.\n"
            "2. После занятия вернись в меню и выбери другую функцию.\n"
            "3. Если работаешь с Gym-Stat, добавь детали тренировки на сайте"
            " для полной истории."
        ),
        parse_mode="HTML",
        reply_markup=get_main_menu(mode=mode)
    )
    context.user_data['conversation_active'] = False
    return ConversationHandler.END

async def show_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отображает меню настроек."""
    if update is None or update.callback_query is None:
        logger.error("Update or callback_query is None in show_settings")
        return ConversationHandler.END

    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    logger.info(f"Пользователь {user_id} открыл настройки")

    mode = 'local'
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
                "• «📏 Мои параметры» — посмотреть замеры тела, сохранённые в Gym-Stat.\n"
                "• «📊 Статистика» — перейти к диаграммам по упражнениям,"
                " тренировкам и весу на сайте Gym-Stat.\n"
            )

        await query.message.edit_text(
            text=(
                "⚙️ <b>Настройки</b>\n"
                f"Текущий режим: <code>{mode_text}</code>\n\n"
                "• «📋 Личные данные» — обнови имя, возраст, вес, рост и пол.\n"
                "• «👤 Показать профиль» — просмотр сохранённых сведений.\n"
                f"{api_hint}"
                "• «⚖️ Данные взвешивания» — история веса из Gym-Stat."
                " Ссылки откроются на сайте Gym-Stat.\n"
                "• «🔙 Назад в главное меню» — вернуться к основным действиям.\n\n"
                "Если разделы пустые, начни с заполнения личных данных или"
                " авторизуйся через /login для синхронизации с сайтом."
            ),
            parse_mode="HTML",
            reply_markup=get_settings_menu(mode=mode)
        )
    except Exception as e:
        logger.error(f"Ошибка в show_settings для пользователя {user_id}: {e}")
        try:
            await query.message.reply_text(
                "⚠️ Произошла ошибка при открытии настроек. Попробуйте снова.",
                reply_markup=get_main_menu(mode=mode),
            )
        except Exception as reply_error:
            logger.error(f"Ошибка при отправке сообщения об ошибке для пользователя {user_id}: {reply_error}")
        return ConversationHandler.END

    context.user_data['conversation_active'] = False
    return ConversationHandler.END

async def show_personal_data_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отображает меню персональных данных."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    logger.info(f"Пользователь {user_id} открыл меню персональных данных")

    await query.message.edit_text(
        (
            "📋 <b>Личные данные</b>\n"
            "1. Выберите показатель из списка ниже.\n"
            "2. Отправьте значение текстом (бот подскажет формат).\n"
            "3. Если ошиблись — введите корректное значение ещё раз или"
            " нажмите /cancel, чтобы выйти.\n\n"
            "• «Имя» — отобразится в приветствиях и профиле.\n"
            "• «Пол» — нужен для персональных рекомендаций.\n"
            "• «Возраст», «Вес», «Рост» — пригодятся в карточке профиля и"
            " при работе с AI-консультантом.\n"
            "• «📊 Параметры тела» — быстрый обзор заполненных значений с"
            " возможностью очистить их.\n"
            "• «🔙 Назад» — вернуться к настройкам."
        ),
        parse_mode="HTML",
        reply_markup=get_personal_data_menu()
    )
    context.user_data['conversation_active'] = False
    return ConversationHandler.END


async def show_statistics_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Показывает меню статистики Gym-Stat."""

    query = update.callback_query
    if not query:
        logger.error("Отсутствует callback_query при показе статистики")
        return ConversationHandler.END

    await query.answer()

    user_id = query.from_user.id
    logger.info("Пользователь %s открыл раздел статистики", user_id)

    try:
        mode = await get_user_mode(user_id)
    except Exception as exc:  # noqa: BLE001
        logger.error("Не удалось определить режим пользователя %s: %s", user_id, exc)
        try:
            await query.message.edit_text(
                "⚠️ Не удалось определить режим работы. Попробуйте позже.",
                reply_markup=get_settings_menu(),
            )
        except Exception as reply_error:  # noqa: BLE001
            logger.error(
                "Ошибка при отправке уведомления пользователю %s: %s",
                user_id,
                reply_error,
            )
        context.user_data['conversation_active'] = False
        return ConversationHandler.END

    if mode != "api":
        await query.message.edit_text(
            "ℹ️ Статистика доступна после входа в Gym-Stat. Выполните /login"
            " и попробуйте снова.",
            parse_mode="HTML",
            reply_markup=get_settings_menu(mode=mode),
        )
        context.user_data['conversation_active'] = False
        return ConversationHandler.END

    await query.message.edit_text(
        (
            "📊 <b>Статистика Gym-Stat</b>\n"
            "• «По упражнениям» — динамика нагрузок по каждому упражнению.\n"
            "• «По тренировкам» — суммарные показатели по занятиям.\n"
            "• «По весу» — графики изменения массы тела.\n"
            "Ссылки откроются в браузере на сайте Gym-Stat. Если окно не"
            " открывается автоматически, воспользуйтесь кнопкой повторно"
            " или скопируйте адрес вручную."
        ),
        parse_mode="HTML",
        reply_markup=get_stats_menu(),
    )
    context.user_data['conversation_active'] = False
    return ConversationHandler.END

async def show_training_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отображает меню настроек тренировок."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    logger.info(f"Пользователь {user_id} открыл настройки тренировок")

    await query.message.edit_text(
        (
            "🏋️ <b>Настройки тренировок</b>\n"
            "Здесь будут появляться дополнительные параметры планирования."
            " Пока доступна заготовка раздела — вы всегда можете вернуться"
            " назад или поделиться пожеланиями через «/contacts»."
        ),
        parse_mode="HTML",
        reply_markup=get_training_settings_menu()
    )
    context.user_data['conversation_active'] = False
    return ConversationHandler.END

async def return_to_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Возвращает пользователя в главное меню."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    logger.info(f"Пользователь {user_id} вернулся в главное меню")

    mode = await get_user_mode(user_id)

    await query.message.edit_text(
        (
            "💪 Готово! Ниже снова главное меню.\n"
            "Если хотите начать с нуля — используйте /start."
            " Помните, что кнопки работают как быстрые ссылки:"
            " достаточно нажать на нужную, чтобы открыть соответствующий"
            " раздел."
        ),
        parse_mode="HTML",
        reply_markup=get_main_menu(mode=mode)
    )
    context.user_data['conversation_active'] = False
    return ConversationHandler.END
