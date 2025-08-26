# message_deletion.py
"""
Импортирует функцию schedule_message_deletion, которая планирует удаление сообщений через указанное время.
"""

import logging
import asyncio
from telegram.ext import ContextTypes


# Инициализация логгера
logger = logging.getLogger(__name__)

async def schedule_message_deletion(
        context: ContextTypes.DEFAULT_TYPE,
        message_ids: list,
        chat_id: int,
        delay: int = 300) -> None:
    """
        Обработчик события "удаление сообщений".
        Описание: Планирует удаление указанных сообщений через заданное время.
        Аргументы:
            context: Контекст выполнения команды, предоставляющий доступ к данным бота.
            message_ids: Список ID сообщений для удаления.
            chat_id: ID чата, в котором находятся сообщения.
            delay: Задержка в секундах перед удалением сообщений (по умолчанию 300 секунд).
        Возвращаемое значение: None
        Исключения:
            telegram.error.TelegramError: Если возникают ошибки при удалении сообщения.
    """
    try:
        # Ожидание заданной задержки
        await asyncio.sleep(delay)

        # Удаление каждого сообщения по его ID
        for message_id in message_ids:
            try:
                await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
                logger.info(f"Сообщение {message_id} удалено из чата {chat_id}")
            except Exception as e:
                logger.error(f"Ошибка при удалении сообщения {message_id} из чата {chat_id}: {e}")

    except Exception as e:
        logger.error(f"Неожиданная ошибка при планировании удаления сообщений в чате {chat_id}: {e}")