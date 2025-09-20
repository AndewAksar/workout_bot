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

from bot.api.gym_stat_client import get_trainings as api_get_trainings
from bot.keyboards.main_menu import get_main_menu
from bot.keyboards.settings_menu import get_settings_menu
from bot.keyboards.personal_data_menu import get_personal_data_menu
from bot.keyboards.training_settings_menu import get_training_settings_menu
from bot.utils.api_session import get_valid_access_token
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
        reply_markup=get_main_menu()
    )
    context.user_data['conversation_active'] = False
    return ConversationHandler.END

async def show_trainings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отображает список тренировок пользователя."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    logger.info(f"Пользователь {user_id} запросил список тренировок")

    mode = await get_user_mode(user_id)

    if mode == 'api':
        token = await get_valid_access_token(user_id)
        if not token:
            await query.message.edit_text(
                (
                    "🔐 История тренировок хранится на Gym-Stat.\n"
                    "Выполните /login или нажмите «Войти», чтобы подтянуть"
                    " занятия с сервера. После авторизации повторно нажмите"
                    " «🗂️ Мои тренировки»."
                ),
                parse_mode="HTML",
                reply_markup=get_main_menu(),
            )
            context.user_data['conversation_active'] = False
            return ConversationHandler.END
        resp = await api_get_trainings(token)
        if resp.status_code == 200:
            trainings = resp.json() or []
            if trainings:
                lines = [
                    "🗂️ <b>Ваши тренировки с Gym-Stat</b>",
                    "Каждая строка — дата и количество записанных упражнений."
                ]
                for training in trainings:
                    lines.append(
                        f"📅 {training.get('date')}: {len(training.get('exercises', []))} упражнений"
                    )
                lines.append(
                    "\nℹ️ Раскройте подробности на сайте Gym-Stat или ведите"
                    " заметки прямо в этом чате после каждой тренировки."
                )
                text = "\n".join(lines)
            else:
                text = (
                    "📭 Пока нет зарегистрированных тренировок."
                    " Нажмите «🏋️‍♂️ Начать тренировку», чтобы создать заметку,"
                    " а на сайте Gym-Stat добавьте подробности — после"
                    " синхронизации они появятся здесь."
                )
            await query.message.edit_text(text, parse_mode="HTML", reply_markup=get_main_menu())
        else:
            await query.message.edit_text(
                (
                    "❌ Не удалось получить список тренировок. Это может"
                    " быть временной ошибкой сервера. Попробуйте чуть позже"
                    " или проверьте, авторизованы ли вы через /login."
                ),
                parse_mode="HTML",
                reply_markup=get_main_menu()
            )
    else:
        await query.message.edit_text(
            (
                "🗂️ В локальном режиме тренировки можно фиксировать сообщениями"
                " вручную. После нажатия «🏋️‍♂️ Начать тренировку» опишите"
                " упражнение, время или ощущения. Когда появится автоматический"
                " журнал, все заметки будут переноситься сюда."
            ),
            parse_mode="HTML",
            reply_markup=get_main_menu(),
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

    try:
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT mode FROM users WHERE user_id = ?",
                (user_id,),
            ) as cursor:
                row = await cursor.fetchone()
        mode = row[0] if row else 'local'
        mode_text = 'Интеграция с Gym-Stat.ru' if mode == 'api' else 'Telegram-версия'

        await query.message.edit_text(
            text=(
                "⚙️ <b>Настройки</b>\n"
                f"Текущий режим: <code>{mode_text}</code>\n\n"
                "• «📋 Личные данные» — обнови имя, возраст, вес, рост и пол.\n"
                "• «👤 Показать профиль» — просмотр сохранённых сведений.\n"
                "• «⚖️ Данные взвешивания» — история веса из Gym-Stat.\n"
                "• «🔙 Назад в главное меню» — вернуться к основным действиям.\n\n"
                "Если разделы пустые, начни с заполнения личных данных или"
                " авторизуйся через /login для синхронизации с сайтом."
            ),
            parse_mode="HTML",
            reply_markup=get_settings_menu()
        )
    except Exception as e:
        logger.error(f"Ошибка в show_settings для пользователя {user_id}: {e}")
        try:
            await query.message.reply_text(
                "⚠️ Произошла ошибка при открытии настроек. Попробуйте снова.",
                reply_markup=get_main_menu(),
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
            "• «🔙 Назад» — вернуться к настройкам."
        ),
        parse_mode="HTML",
        reply_markup=get_personal_data_menu()
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

    await query.message.edit_text(
        (
            "💪 Готово! Ниже снова главное меню.\n"
            "Если хотите начать с нуля — используйте /start."
            " Помните, что кнопки работают как быстрые ссылки:"
            " достаточно нажать на нужную, чтобы открыть соответствующий"
            " раздел."
        ),
        parse_mode="HTML",
        reply_markup=get_main_menu()
    )
    context.user_data['conversation_active'] = False
    return ConversationHandler.END