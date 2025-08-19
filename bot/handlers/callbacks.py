# bot/handlers/callbacks.py
from telegram import Update
from telegram.ext import ContextTypes


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "start_training":
        await query.message.reply_text(
            "🏋️‍♂️ Тренировка начата! Следуйте инструкциям или добавьте свои упражнения."
        )
    elif query.data == "my_trainings":
        await query.message.reply_text(
            "🗂️ Здесь будут отображаться ваши тренировки (функция в разработке)."
        )
    elif query.data == "settings":
        await query.message.reply_text(
            "⚙️ Настройки бота (функция в разработке)."
        )