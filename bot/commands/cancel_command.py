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
import asyncio

from bot.keyboards.settings_menu import get_settings_menu
from bot.keyboards.main_menu import get_main_menu
from bot.utils.message_deletion import schedule_message_deletion
from bot.utils.db_utils import get_user_mode
from bot.utils.logger import setup_logging


logger = setup_logging()

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обработчик команды /cancel.
    Описание: Завершает активный диалог и очищает временные данные.
              Вне диалога информирует пользователя об отсутствии действия для отмены.
              Команда /cancel удаляется через 5 секунд. При отсутствии диалога удаляется
              также сообщение с уведомлением. При ошибке или успешной отмене в диалоге
              показывается сообщение, удаляется через 5 секунд, затем отображается меню настроек.
    Аргументы:
        update (telegram.Update): Объект обновления, содержащий команду /cancel.
        context (telegram.ext.ContextTypes.DEFAULT_TYPE): Контекст выполнения команды.
    Возвращаемое значение:
        int: ConversationHandler.END, завершающий диалог.
    Пример использования:
        Пользователь отправляет /cancel:
            - В диалоге: завершает диалог, показывает сообщение об отмене, удаляет его через 5 секунд,
                          затем показывает меню настроек.
            - Вне диалога: уведомляет, что нет активного диалога, удаляет сообщение через 5 секунд,
                          затем показывает меню настроек.
            - При ошибке: показывает сообщение об ошибке, удаляет его через 5 секунд,
                          затем показывает меню настроек.
    """
    user_id = update.message.from_user.id
    chat_id = update.message.chat_id
    message_id = update.message.message_id

    mode = "local"
    try:
        # Проверяем, есть ли активный диалог
        is_conversation_active = context.user_data.get('conversation_active', False)
        message_ids = [message_id]  # Список для удаления, включает команду /cancel

        # Сбрасываем флаг диалога и другие временные данные
        context.user_data.clear()  # Полная очистка user_data для избежания конфликтов

        if is_conversation_active:
            # В диалоге: отменяем и показываем сообщение
            message_text = "❌ Действие отменено! Диалог завершен."
            logger.info(f"Пользователь {user_id} отменил активный диалог.")
        else:
            # Вне диалога: уведомляем, что нет активного диалога
            message_text = "ℹ️ Нет активного диалога для отмены."
            logger.info(f"Пользователь {user_id} вызвал /cancel без активного диалога.")

        # Отправляем сообщение и сохраняем его ID
        sent_message = await update.message.reply_text(
            message_text,
            parse_mode="HTML"
        )
        message_ids.append(sent_message.message_id)

        # Планируем удаление сообщений
        logger.info(f"Планируется удаление сообщений {message_ids} в чате {chat_id}")
        schedule_message_deletion(
            context,
            message_ids,
            chat_id=chat_id,
            delay=5
        )

        # Определяем режим пользователя для меню настроек
        try:
            mode = await get_user_mode(user_id)
        except Exception as mode_error:  # noqa: BLE001
            logger.error(f"Не удалось определить режим пользователя {user_id}: {mode_error}")
            mode = "local"

        # Отправляем меню настроек после задержки
        await asyncio.sleep(5)
        await context.bot.send_message(
            chat_id=chat_id,
            text="⚙️ Возвращаемся в меню настроек.",
            reply_markup=get_settings_menu(mode=mode),
            parse_mode="HTML"
        )

    except Exception as e:
        logger.error(f"Ошибка при обработке команды /cancel: {e}")
        try:
            # Отправляем сообщение об ошибке без меню
            error_message = await update.message.reply_text(
                "❌ Произошла ошибка при отмене.",
                parse_mode="HTML"
            )
            # Планируем удаление команды /cancel и сообщения об ошибке
            message_ids = [message_id, error_message.message_id]
            schedule_message_deletion(
                context,
                message_ids,
                chat_id=chat_id,
                delay=5
            )
            # Определяем режим пользователя для меню настроек
            try:
                mode = await get_user_mode(user_id)
            except Exception as mode_error:
                logger.error(f"Не удалось определить режим пользователя {user_id}: {mode_error}")
                mode = "local"
            # Отправляем меню настроек после задержки
            await asyncio.sleep(5)
            await context.bot.send_message(
                chat_id=chat_id,
                text="⚙️ Возвращаемся в меню настроек.",
                reply_markup=get_settings_menu(mode=mode),
                parse_mode="HTML"
            )
        except Exception as e2:
            logger.error(f"Ошибка при отправке сообщения об ошибке для {user_id}: {str(e2)}")

    logger.debug(f"Состояние после /cancel для пользователя {user_id}: {context.user_data}")
    return ConversationHandler.END