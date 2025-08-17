# main.py
import logging
from os import environ
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from dotenv import load_dotenv


# Настройка логирования
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

# Токен вашего бота
TOKEN = environ.get('TELEGRAM_TOKEN')

# Список разрешенных user_id (добавьте сюда ID пользователей)
ALLOWED_USER_IDS = {344325575}  # Замените на реальные ID

# Проверка авторизации
def is_user_authorized(user_id: int) -> bool:
    return user_id in ALLOWED_USER_IDS

# Обработчик команды /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_user_authorized(user_id):
        await update.message.reply_text("🚫 Доступ запрещен. Ваш ID не в списке разрешенных пользователей.")
        logger.warning(f"Неавторизованный доступ: user_id={user_id}")
        return

    # Создание красивого меню с инлайн-кнопками на всю ширину
    keyboard = [
        [InlineKeyboardButton("🏋️‍♂️ Начать тренировку", callback_data='start_training')],
        [InlineKeyboardButton("🗂️ Мои тренировки", callback_data='my_trainings')],
        [InlineKeyboardButton("⚙️ Настройки", callback_data='settings')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "💪 Добро пожаловать в бот для тренировок!\n"
        "Выберите действие в меню ниже:",
        reply_markup=reply_markup
    )

# Обработчик нажатия кнопки
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id

    if not is_user_authorized(user_id):
        await query.answer("🚫 Доступ запрещен. Ваш ID не в списке разрешенных пользователей.")
        return

    await query.answer()  # Подтверждение нажатия кнопки
    if query.data == "start_training":
        await query.message.reply_text("🏋️‍♂️ Тренировка начата! Следуйте инструкциям или добавьте свои упражнения.")
    elif query.data == "my_trainings":
        await query.message.reply_text("🗂️ Здесь будут отображаться ваши тренировки (функция в разработке).")
    elif query.data == "settings":
        await query.message.reply_text("⚙️ Настройки бота (функция в разработке).")

# Обработчик команды /help
async def help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"Команды бота:\n"
        f"/start - Начать работу с ботом\n"
        f"/help - Показать это сообщение\n"
        f"/contacts - Контакты с владельцем\n\n"
        f"ВНИМАНИЕ!\n"
        f"Бот доступен только для авторизованных пользователей.\n"
        f"Если Вы не являетесь членом клуба фанатов Алекса Лесли, то к сожалению Вам будет отказано в доступе.\n"
    )

# Обработчик команды /contact
async def contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"Контакты с владельцем:\n"
        f"Телеграм: @dedandrew\n"
    )

# Основная функция
def main() -> None:
    """Запускает бота."""
    application = Application.builder().token(TOKEN).build()

    # Регистрация обработчиков команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help))
    application.add_handler(CommandHandler("contacts", contact))
    application.add_handler(CallbackQueryHandler(button_callback))

    # Запуск бота
    application.run_polling(allowed_updates=Update.ALL_TYPES)

# Запуск модуля
if __name__ == '__main__':
    main()