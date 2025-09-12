# bot/handlers/cancel_command.py
"""
Модуль: cancel_command.py
Описание: Модуль содержит обработчик команды /cancel для завершения активных диалогов.

Зависимости:
- telegram: Для взаимодействия с Telegram API.
- telegram.ext: Для работы с контекстом и обновлениями Telegram.
- bot.keyboards.main_menu: Для возврата в главное меню.
- bot.utils.message_deletion: Для планирования удаления сообщений.
- bot.utils.logger: Для логирования событий.
"""

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from bot.keyboards.settings_menu import get_settings_menu
from bot.keyboards.main_menu import get_main_menu
from bot.utils.message_deletion import schedule_message_deletion
from bot.utils.logger import setup_logging


logger = setup_logging()

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обработчик команды /cancel.
    Описание: Завершает активный диалог и очищает временные данные.
              Вне диалога информирует пользователя об отсутствии действия для отмены.
              Команда /cancel удаляется через 5 секунд. При отсутствии диалога удаляется
              также сообщение с уведомлением.
    Аргументы:
        update (telegram.Update): Объект обновления, содержащий команду /cancel.
        context (telegram.ext.ContextTypes.DEFAULT_TYPE): Контекст выполнения команды.
    Возвращаемое значение:
        int: ConversationHandler.END, завершающий диалог.
    Пример использования:
        Пользователь отправляет /cancel:
            - В диалоге: завершает диалог, показывает главное меню.
            - Вне диалога: уведомляет, что нет активного диалога, показывает главное меню.
        В любом случае команда /cancel удаляется через 5 секунд.
            - В диалоге: завершает диалог, показывает меню настроек.
            - Вне диалога: уведомляет, что нет активного диалога.
    """
    user_id = update.message.from_user.id
    chat_id = update.message.chat_id
    message_id = update.message.message_id

    try:
        # Проверяем, есть ли активный диалог
        is_conversation_active = context.user_data.get('conversation_active', False)
        message_ids = [message_id]  # Список для удаления, включает команду /cancel

        # Сбрасываем флаг диалога и другие временные данные
        context.user_data.clear()  # Полная очистка user_data для избежания конфликтов

        if is_conversation_active:
            # В диалоге: отменяем и показываем меню настроек
            message_text = "❌ Действие отменено."
            reply_markup = get_settings_menu()
            logger.info(f"Пользователь {user_id} отменил активный диалог.")
        else:
            # Вне диалога: уведомляем, что нет активного диалога
            message_text = "ℹ️ Нет активного диалога для отмены."
            reply_markup = None  # Без меню
            logger.info(f"Пользователь {user_id} вызвал /cancel без активного диалога.")

        # Отправляем сообщение и сохраняем его ID
        sent_message = await update.message.reply_text(
            message_text,
            reply_markup=reply_markup,
            parse_mode="HTML"
        )

        # Если вне диалога, добавляем ID отправленного сообщения в список для удаления
        if not is_conversation_active:
            message_ids.append(sent_message.message_id)

        # Планируем удаление сообщений
        logger.info(f"Планируется удаление сообщений {message_ids} в чате {chat_id}")
        await schedule_message_deletion(
            context,
            message_ids,
            chat_id=chat_id,
            delay=5
        )

    except Exception as e:
        logger.error(f"Ошибка при обработке команды /cancel: {e}")
        try:
            await update.message.reply_text(
                "❌ Произошла ошибка при отмене. Возвращаемся в главное меню.",
                reply_markup=get_main_menu(),
                parse_mode="HTML"
            )
            # Планируем удаление команды /cancel даже при ошибке
            await schedule_message_deletion(
                context,
                [message_id],
                chat_id=chat_id,
                delay=5
            )
        except Exception as e2:
            logger.error(f"Ошибка при отправке сообщения об ошибке для {user_id}: {str(e2)}")

    logger.debug(f"Состояние после /cancel для пользователя {user_id}: {context.user_data}")
    return ConversationHandler.END