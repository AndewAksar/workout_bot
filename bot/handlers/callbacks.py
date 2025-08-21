# bot/handlers/callbacks.py
import sqlite3
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, filters

from bot.keyboards.main_menu import get_main_menu
from bot.keyboards.settings_menu import (get_settings_menu, get_personal_data_menu,
                                         get_training_settings_menu, get_ai_assistant_menu)
from bot.utils.logger import setup_logging


logger = setup_logging()

# Состояния для ConversationHandler
SET_NAME, SET_AGE, SET_WEIGHT, SET_HEIGHT, SET_TRAINING_TYPE = range(5)

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    logger.info(f"Пользователь {user_id} нажал кнопку: {query.data}")

    # Подключение к базе данных
    conn = sqlite3.connect('users.db')
    c = conn.cursor()

    if query.data == "start_training":
        await query.message.edit_text(
            "🏋️‍♂️ Тренировка начата! Следуйте инструкциям или добавьте свои упражнения.",
            reply_markup=get_main_menu()
        )
    elif query.data == "my_trainings":
        await query.message.edit_text(
            "🗂️ Здесь будут отображаться ваши тренировки (функция в разработке).",
            reply_markup=get_main_menu()
        )
    elif query.data == "my_ai_assistant":
        await query.message.edit_text(
            "🤖 Здесь можно будет воспользоваться AI-консультантом.",
            reply_markup=get_ai_assistant_menu()
        )
    elif query.data == "settings":
        await query.message.edit_text(
            "⚙️ Настройки профиля:",
            reply_markup=get_settings_menu()
        )
    elif query.data == "personal_data":
        await query.message.edit_text(
            "📋 Выберите, что хотите изменить:",
            reply_markup=get_personal_data_menu()
        )
    elif query.data == "training_settings":
        await query.message.edit_text(
            "🏋️ Настройки тренировок:",
            reply_markup=get_training_settings_menu()
        )
    elif query.data == "show_profile":
        c.execute("SELECT name, age, weight, height, training_type, username FROM UserSettings WHERE user_id = ?",
                  (user_id,))
        profile = c.fetchone()
        if profile:
            greeting = (
                f"<b>Ваш профиль:</b>\n"
                f"👤 Имя: {profile[0] if profile[0] else 'Не указано'}\n"
                f"🎂 Возраст: {profile[1] if profile[1] else 'Не указан'}\n"
                f"⚖️ Вес: {profile[2] if profile[2] else 'Не указан'} кг\n"
                f"📏 Рост: {profile[3] if profile[3] else 'Не указан'} см\n"
                f"💪 Тип тренировок: {profile[4] if profile[4] else 'Не указан'}\n"
                f"📧 Telegram: @{profile[5] if profile[5] else 'Не указан'}"
            )
        else:
            greeting = "⚠️ Профиль не найден. Пожалуйста, используйте /start для инициализации."
        await query.message.edit_text(
            greeting,
            parse_mode="HTML",
            reply_markup=get_settings_menu()
        )
    elif query.data == "main_menu":
        await query.message.edit_text(
            "💪 Выберите действие в меню ниже:",
            reply_markup=get_main_menu()
        )
    elif query.data == "set_name":
        await query.message.edit_text(
            "✍️ Введите ваше имя:",
            reply_markup=None
        )
        return SET_NAME
    elif query.data == "set_age":
        await query.message.edit_text(
            "🎂 Введите ваш возраст (число):",
            reply_markup=None
        )
        return SET_AGE
    elif query.data == "set_weight":
        await query.message.edit_text(
            "⚖️ Введите ваш вес в кг (например, 70.5):",
            reply_markup=None
        )
        return SET_WEIGHT
    elif query.data == "set_height":
        await query.message.edit_text(
            "📏 Введите ваш рост в см (например, 175):",
            reply_markup=None
        )
        return SET_HEIGHT
    elif query.data == "set_training_type":
        await query.message.edit_text(
            "💪 Введите тип тренировок (например, силовые, кардио, йога):",
            reply_markup=None
        )
        return SET_TRAINING_TYPE

    conn.close()
    return ConversationHandler.END

# Обработчики для ввода данных
async def set_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    name = update.message.text.strip()
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("UPDATE UserSettings SET name = ? WHERE user_id = ?", (name, user_id))
    conn.commit()
    conn.close()
    await update.message.reply_text(
        f"✅ Имя обновлено: {name}",
        reply_markup=get_personal_data_menu()
    )
    return ConversationHandler.END

async def set_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    try:
        age = int(update.message.text.strip())
        if age < 0 or age > 150:
            raise ValueError("Некорректный возраст")
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute("UPDATE UserSettings SET age = ? WHERE user_id = ?", (age, user_id))
        conn.commit()
        conn.close()
        await update.message.reply_text(
            f"✅ Возраст обновлен: {age}",
            reply_markup=get_personal_data_menu()
        )
    except ValueError:
        await update.message.reply_text(
            "⚠️ Пожалуйста, введите корректное число для возраста.",
            reply_markup=get_personal_data_menu()
        )
    return ConversationHandler.END

async def set_weight(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    try:
        weight = float(update.message.text.strip())
        if weight < 0 or weight > 500:
            raise ValueError("Некорректный вес")
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute("UPDATE UserSettings SET weight = ? WHERE user_id = ?", (weight, user_id))
        conn.commit()
        conn.close()
        await update.message.reply_text(
            f"✅ Вес обновлен: {weight} кг",
            reply_markup=get_personal_data_menu()
        )
    except ValueError:
        await update.message.reply_text(
            "⚠️ Пожалуйста, введите корректное число для веса (например, 70.5).",
            reply_markup=get_personal_data_menu()
        )
    return ConversationHandler.END

async def set_height(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    try:
        height = float(update.message.text.strip())
        if height < 0 or height > 300:
            raise ValueError("Некорректный рост")
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute("UPDATE UserSettings SET height = ? WHERE user_id = ?", (height, user_id))
        conn.commit()
        conn.close()
        await update.message.reply_text(
            f"✅ Рост обновлен: {height} см",
            reply_markup=get_personal_data_menu()
        )
    except ValueError:
        await update.message.reply_text(
            "⚠️ Пожалуйста, введите корректное число для роста (например, 175).",
            reply_markup=get_personal_data_menu()
        )
    return ConversationHandler.END

async def set_training_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    training_type = update.message.text.strip()
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("UPDATE UserSettings SET training_type = ? WHERE user_id = ?", (training_type, user_id))
    conn.commit()
    conn.close()
    await update.message.reply_text(
        f"✅ Тип тренировок обновлен: {training_type}",
        reply_markup=get_training_settings_menu()
    )
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🔙 Действие отменено.",
        reply_markup=get_settings_menu()
    )
    return ConversationHandler.END