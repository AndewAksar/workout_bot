# bot/utils/message_deletion.py
"""
Импортирует функцию schedule_message_deletion, которая планирует удаление сообщений через указанное время.
"""

import asyncio
import logging
from telegram.ext import ContextTypes


# Инициализация логгера
logger = logging.getLogger(__name__)


def schedule_message_deletion(
    context: ContextTypes.DEFAULT_TYPE,
    message_ids: list[int],
    chat_id: int,
    delay: int = 300,
) -> None:
    """Запускает задачу удаления сообщений без блокировки хендлера."""
    async def _delete_later() -> None:
        try:
            await asyncio.sleep(delay)

            for message_id in message_ids:
                try:
                    await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
                    logger.info(f"Сообщение {message_id} удалено из чата {chat_id}")
                except Exception as e:
                    logger.error(
                        f"Ошибка при удалении сообщения {message_id} из чата {chat_id}: {e}"
                    )

        except Exception as e:
            logger.error(
                f"Неожиданная ошибка при планировании удаления сообщений в чате {chat_id}: {e}"
            )
    try:
        asyncio.create_task(_delete_later())
    except RuntimeError as e:
        logger.error(
            f"Не удалось запланировать удаление сообщений в чате {chat_id}: {e}"
        )