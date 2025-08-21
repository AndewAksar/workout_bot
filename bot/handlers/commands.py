# bot/handlers/commands.py
import sqlite3
from telegram import Update
from telegram.ext import ContextTypes

from bot.config.settings import TELEGRAM_TOKEN, WELCOME_MESSAGE
from bot.keyboards.main_menu import get_main_menu
from bot.keyboards.settings_menu import get_settings_menu, get_personal_data_menu, get_training_settings_menu


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    user_id = user.id
    username = user.username if user.username else "друг"
    first_name = user.first_name if user.first_name else ""

    # Сохраняем или обновляем данные пользователя в базе
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO UserSettings (user_id, username, name) VALUES (?, ?, ?)",
              (user_id, username, first_name))
    conn.commit()

    # Получаем данные профиля
    c.execute("SELECT name, age, weight, height, training_type FROM UserSettings WHERE user_id = ?",
              (user_id,))
    profile = c.fetchone()
    conn.close()

    greeting = (
        f"<b>Привет, {profile[0] or username}! 👋</b>\n"
        f"Твой ID: <code>{user_id}</code>\n"
    )
    if profile and any(profile[1:]):  # Если есть дополнительные данные
        greeting += (
            f"\n📋 <b>Твой профиль:</b>\n"
            f"Возраст: {profile[1] if profile[1] else 'Не указан'}\n"
            f"Вес: {profile[2] if profile[2] else 'Не указан'} кг\n"
            f"Рост: {profile[3] if profile[3] else 'Не указан'} см\n"
            f"Тип тренировок: {profile[4] if profile[4] else 'Не указан'}\n"
        )
    greeting += f"{WELCOME_MESSAGE}"

    await update.message.reply_text(
        greeting,
        parse_mode="HTML",  # Включаем HTML-разметку
        reply_markup=get_main_menu()
    )

async def help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Команды бота:\n"
        "/start - Начать работу с ботом\n"
        "/settings - Настроить профиль\n\n"
        "/contacts - Контакты с владельцем\n\n"
    )

# Обработчик команды /contact
async def contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"📞 <b>Контакты владельца:</b>\n"
        f"Телеграм: <a href='https://t.me/dedandrew'>@dedandrew</a>\n",
        parse_mode="HTML"
    )

async def settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⚙️ Настройки профиля:",
        reply_markup=get_settings_menu()
    )