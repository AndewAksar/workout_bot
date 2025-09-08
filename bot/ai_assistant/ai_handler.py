# bot/handlers/ai_handler.py
"""
Модуль: ai_handler.py
Описание: Модуль содержит обработчики для взаимодействия с AI-ассистентом в Telegram-боте.
Обеспечивает запуск, обработку сообщений и завершение консультации с AI через ConversationHandler.

Зависимости:
- telegram: Для взаимодействия с Telegram API.
- telegram.ext: Для работы с контекстом, обработчиками и ConversationHandler.
- bot.utils.logger: Для настройки логирования.
- bot.keyboards.main_menu: Для получения клавиатуры главного меню.
- bot.ai_assistant.ai_api: Для взаимодействия с API GigaChat.
- bot.ai_assistant.ai_prompt: Для получения системного промпта.
"""

import logging
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,

)
from telegram.error import TelegramError
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
)
from telegram.constants import ParseMode

from bot.utils.logger import setup_logging
from bot.keyboards.main_menu import get_main_menu
from bot.keyboards.ai_assistant_menu import get_model_selection_menu
from bot.ai_assistant.ai_api import (
    generate_gigachat_response,
    get_user_settings
)
from bot.ai_assistant.open_ai_bot import generate_chatgpt_response
from bot.ai_assistant.ai_prompt import get_system_prompt
from bot.utils.message_deletion import schedule_message_deletion
from bot.config.settings import AI_CONSULTATION


logger = setup_logging()

# Глобальная переменная для хранения токена
GIGACHAT_AUTH_TOKEN = None

# Ограничение на длину сообщения
MAX_MESSAGE_LENGTH = 4096

# Меню выбора модели
async def choose_ai_model(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Предлагает пользователю выбрать языковую модель."""
    query = update.callback_query
    await query.answer()
    await query.message.edit_text(
        "🤖 Выберите языковую модель для консультации:",
        reply_markup=get_model_selection_menu(),
    )
    return ConversationHandler.END

async def start_gigachat_assistant(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Запуск консультации с моделью GigaChat."""
    context.user_data['ai_model'] = 'gigachat'
    return await start_ai_assistant(update, context)

async def start_chatgpt_assistant(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Запуск консультации с моделью ChatGPT."""
    context.user_data['ai_model'] = 'chatgpt'
    return await start_ai_assistant(update, context)

# Обработчик запуска консультации с AI после выбора модели
async def start_ai_assistant(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    logger.info(f"Пользователь {user_id} начал консультацию с AI-ассистентом.")

    context.user_data['conversation_active'] = True
    context.user_data['current_state'] = 'AI_CONSULTATION'
    context.user_data['ai_history'] = []

    model = context.user_data.get('ai_model', 'gigachat')
    model_name = 'ChatGPT' if model == 'chatgpt' else 'GigaChat'

    exit_keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🚪 Завершить консультацию", callback_data='end_ai_consultation')]
    ])

    # Объединяем текст в одну строку
    message_text = (
        f"🤖 Вы выбрали {model_name}. Задайте свой вопрос по тренировкам, питанию или мотивации.\n\n"
        "Чтобы завершить, нажмите кнопку ниже."
    )

    message = await query.message.edit_text(
        text=message_text,
        parse_mode=ParseMode.HTML,
        reply_markup=exit_keyboard
    )
    context.user_data['start_ai_message_id'] = message.message_id
    logger.debug(f"Сохранён message_id начального сообщения: {message.message_id}")

    return AI_CONSULTATION

# Обработчик сообщений во время консультации
async def handle_ai_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обработчик текстовых сообщений во время консультации с AI.
    Аргументы:
        update (telegram.Update): Объект обновления Telegram.
        context (telegram.ext.ContextTypes.DEFAULT_TYPE): Контекст выполнения.
    Возвращаемое значение:
        int: Состояние AI_CONSULTATION для продолжения диалога.
    """
    user_message = update.message.text
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    logger.info(f"Пользователь {user_id} спросил AI: {user_message}")

    # Проверяем, что бот находится в состоянии AI_CONSULTATION
    if context.user_data.get('current_state') != 'AI_CONSULTATION':
        logger.warning(f"Некорректное состояние для handle_ai_message: {context.user_data.get('current_state')}")
        await update.message.reply_text(
            "⚠️ Пожалуйста, начните консультацию с AI заново.",
            reply_markup=get_main_menu(),
            parse_mode=ParseMode.HTML
        )
        return ConversationHandler.END

    # Клавиатура с кнопкой завершения консультации
    exit_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🚪 Завершить консультацию", callback_data='end_ai_consultation')]
        ])

    try:
        # Получаем данные пользователя из БД
        settings = get_user_settings(user_id)
        user_data_str = ""
        if settings:
            user_data_str = "\nДанные пользователя:\n"
            for key, value in settings.items():
                if value is not None:
                    user_data_str += f"{key.capitalize()}: {value}\n"

        # Формируем системный промпт
        system_prompt = get_system_prompt() + user_data_str

        # Добавляем сообщение пользователя в историю
        context.user_data['ai_history'].append({"role": "user", "content": user_message})

        # Формируем полный список сообщений для API
        messages = [{"role": "system", "content": system_prompt}] + context.user_data['ai_history']

        # Получаем ответ от выбранной модели
        model = context.user_data.get('ai_model', 'gigachat')
        if model == 'chatgpt':
            response = generate_chatgpt_response(messages)
            logger.debug(f"Длина ответа от ChatGPT: {len(response)} символов")
        else:
            response = generate_gigachat_response(messages)
            logger.debug(f"Длина ответа от GigaChat: {len(response)} символов")

        # Добавляем ответ assistant в историю
        context.user_data['ai_history'].append({"role": "assistant", "content": response})

        # Удаляем клавиатуру из начального сообщения (если ещё не удалена)
        start_message_id = context.user_data.get('start_ai_message_id')
        if start_message_id and not context.user_data.get('start_keyboard_removed', False):
            try:
                await context.bot.edit_message_reply_markup(
                    chat_id=chat_id,
                    message_id=start_message_id,
                    reply_markup=None
                )
                logger.debug(f"Клавиатура удалена из начального сообщения {start_message_id}")
                context.user_data['start_keyboard_removed'] = True
            except Exception as e:
                logger.error(f"Ошибка при удалении клавиатуры из начального сообщения {start_message_id}: {e}")

        # Удаляем клавиатуру из предыдущего ответа ИИ
        last_ai_response_id = context.user_data.get('last_ai_response_id')
        if last_ai_response_id:
            try:
                await context.bot.edit_message_reply_markup(
                    chat_id=chat_id,
                    message_id=last_ai_response_id,
                    reply_markup=None
                )
                logger.debug(f"Клавиатура удалена из предыдущего ответа ИИ {last_ai_response_id}")
            except Exception as e:
                logger.error(f"Ошибка при удалении клавиатуры из предыдущего ответа ИИ {last_ai_response_id}: {e}")

        # Разделяем ответ, если он превышает лимит Telegram
        if len(response) <= MAX_MESSAGE_LENGTH:
            sent_message = await update.message.reply_text(
                response,
                parse_mode=None,
                reply_markup=exit_keyboard
            )
            context.user_data['last_ai_response_id'] = sent_message.message_id  # Сохраняем ID последнего ответа
            logger.debug(f"Сохранён last_ai_response_id: {sent_message.message_id}")
        else:
            # Разбиваем текст на части по MAX_MESSAGE_LENGTH
            messages = []
            start = 0
            while start < len(response):
                # Определяем конец текущей части
                end = min(start + MAX_MESSAGE_LENGTH, len(response))
                # Проверяем, не начинается ли следующая часть с пробела или в середине слова
                if end < len(response):
                    # Ищем ближайший пробел или конец предложения для корректной обрезки
                    while end > start and response[end - 1] not in [' ', '\n', '.']:
                        end -= 1
                    # Если не нашли подходящий разделитель, используем MAX_MESSAGE_LENGTH
                    if end == start:
                        end = start + MAX_MESSAGE_LENGTH
                part = response[start:end]
                # Убедимся, что часть не пустая
                if part.strip():
                    is_last_part = end >= len(response)
                    sent_message = await update.message.reply_text(
                        part,
                        parse_mode=None,
                        reply_markup=exit_keyboard if is_last_part else None
                    )
                    messages.append(sent_message.message_id)
                start = end
                # Пропускаем пробелы или переносы строк в начале следующей части
                while start < len(response) and response[start] in [' ', '\n']:
                    start += 1
            if messages:
                context.user_data['last_ai_response_id'] = messages[-1]  # Сохраняем ID последнего сообщения с клавиатурой
                logger.debug(f"Сохранён last_ai_response_id для разбитого ответа: {messages[-1]}")

        return AI_CONSULTATION  # Остаемся в состоянии для продолжения диалога
    except Exception as e:
        logger.error(f"Ошибка в handle_ai_message для пользователя {user_id}: {e}")
        await update.callback_query.message.reply_text(
            "⚠️ Произошла ошибка. Консультация завершена.",
            parse_mode=ParseMode.HTML
        )

        # Сбрасываем флаг диалога
        context.user_data['conversation_active'] = False
        return ConversationHandler.END

# Обработчик завершения консультации (по callback_data='end_ai_consultation')
async def end_ai_consultation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обработчик завершения консультации с AI.
    Аргументы:
        update (telegram.Update): Объект обновления Telegram.
        context (telegram.ext.ContextTypes.DEFAULT_TYPE): Контекст выполнения.
    Возвращаемое значение:
        int: ConversationHandler.END для завершения диалога.
    """
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    logger.info(f"Пользователь {user_id} завершил консультацию с AI-ассистентом.")

    # Удаляем клавиатуру "Завершить консультацию" из последнего сообщения
    try:
        await query.message.edit_reply_markup(reply_markup=None)
        logger.debug(f"Клавиатура удалена из сообщения {query.message.message_id} для пользователя {user_id}")
    except Exception as e:
        logger.error(f"Ошибка при удалении клавиатуры из сообщения {query.message.message_id}: {e}")

    # Отправляем новое сообщение с главным меню
    await query.message.reply_text(
        "🤖 Консультация завершена. Возвращаемся в главное меню.",
        reply_markup=get_main_menu(),
        parse_mode=ParseMode.HTML
    )

    # Сбрасываем флаг диалога и очищаем историю
    context.user_data['conversation_active'] = False
    if 'ai_history' in context.user_data:
        del context.user_data['ai_history']
    if 'start_ai_message_id' in context.user_data:
        del context.user_data['start_ai_message_id']
    if 'last_ai_response_id' in context.user_data:
        del context.user_data['last_ai_response_id']
    if 'start_keyboard_removed' in context.user_data:
        del context.user_data['start_keyboard_removed']
    if 'ai_model' in context.user_data:
        del context.user_data['ai_model']

    return ConversationHandler.END

# Обработчик ошибок для AI
async def ai_error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик ошибок для AI-ассистента."""
    error = context.error
    logger.error(f"Ошибка в AI-ассистенте: {error}")

    if isinstance(error, TelegramError) and "Message is not modified" in str(error):
        # Игнорируем ошибку "Message is not modified", чтобы не прерывать другие действия
        logger.debug("Ошибка 'Message is not modified' проигнорирована")
        return

    # Проверяем, что update существует
    if update is None:
        logger.error("Update is None in ai_error_handler")
        # Сбрасываем состояние, но не отправляем сообщение, так как нет chat_id
        context.user_data['conversation_active'] = False
        if 'ai_history' in context.user_data:
            del context.user_data['ai_history']
        if 'start_ai_message_id' in context.user_data:
            del context.user_data['start_ai_message_id']
        if 'last_ai_response_id' in context.user_data:
            del context.user_data['last_ai_response_id']
        if 'start_keyboard_removed' in context.user_data:
            del context.user_data['start_keyboard_removed']
        if 'ai_model' in context.user_data:
            del context.user_data['ai_model']
        return

    chat_id = None
    user_id = None

    if update.callback_query:
        user_id = update.callback_query.from_user.id
        chat_id = update.callback_query.message.chat_id
    elif update.message:
        user_id = update.message.from_user.id
        chat_id = update.message.chat_id
    else:
        logger.error("Update не содержит ни callback_query, ни message")
        # Сбрасываем состояние
        context.user_data['conversation_active'] = False
        if 'ai_history' in context.user_data:
            del context.user_data['ai_history']
        if 'start_ai_message_id' in context.user_data:
            del context.user_data['start_ai_message_id']
        if 'last_ai_response_id' in context.user_data:
            del context.user_data['last_ai_response_id']
        if 'start_keyboard_removed' in context.user_data:
            del context.user_data['start_keyboard_removed']
        if 'ai_model' in context.user_data:
            del context.user_data['ai_model']
        return

    try:
        message = await context.bot.send_message(
            chat_id=chat_id,
            text="⚠️ Произошла ошибка. Попробуйте снова.",
            reply_markup=get_main_menu(),
            parse_mode = ParseMode.HTML
        )
        await schedule_message_deletion(context, [message.message_id], chat_id, delay=5)

    except Exception as send_error:
        logger.error(f"Ошибка при отправке сообщения об ошибке в чате {chat_id}: {send_error}")

    # Сбрасываем состояние
    context.user_data['conversation_active'] = False
    if 'ai_history' in context.user_data:
        del context.user_data['ai_history']
    if 'start_ai_message_id' in context.user_data:
        del context.user_data['start_ai_message_id']
    if 'last_ai_response_id' in context.user_data:
        del context.user_data['last_ai_response_id']
    if 'start_keyboard_removed' in context.user_data:
        del context.user_data['start_keyboard_removed']
    if 'ai_model' in context.user_data:
        del context.user_data['ai_model']

    return ConversationHandler.END