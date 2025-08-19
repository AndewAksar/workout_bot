# bot/handlers/commands.py
from telegram import Update
from telegram.ext import ContextTypes

from bot.config.settings import TELEGRAM_TOKEN, WELCOME_MESSAGE
from bot.keyboards.main_menu import get_main_menu


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        WELCOME_MESSAGE,
        reply_markup=get_main_menu()
    )

async def help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Команды бота:\n"
        "/start - Начать работу с ботом\n"
        "/help - Показать это сообщение\n"
        "/contacts - Контакты с владельцем\n\n"
    )

# Обработчик команды /contact
async def contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"Контакты с владельцем:\n"
        f"Телеграм: @dedandrew\n"
    )