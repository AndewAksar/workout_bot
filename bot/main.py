# bot/main.py
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler

from config.settings import TELEGRAM_TOKEN
from utils.logger import setup_logging
from handlers.commands import start, help, contact
from handlers.callbacks import button_callback


logger = setup_logging()

def main() -> None:
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # Добавляем обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help))
    application.add_handler(CommandHandler("contacts", contact))
    application.add_handler(CallbackQueryHandler(button_callback))

    logger.info("Бот запущен")

    # Запускаем polling, передавая управление событийным циклом
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()