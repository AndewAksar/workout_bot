from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def get_settings_menu():
    keyboard = [
        [
            InlineKeyboardButton("📋 Личные данные", callback_data='personal_data'),
            InlineKeyboardButton("🏋️ Тренировки", callback_data='training_settings')
        ],
        [InlineKeyboardButton("👤 Показать профиль", callback_data='show_profile')],
        [InlineKeyboardButton("🔙 Назад в главное меню", callback_data='main_menu')]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_personal_data_menu():
    keyboard = [
        [
            InlineKeyboardButton("✍️ Имя", callback_data='set_name'),
            InlineKeyboardButton("🎂 Возраст", callback_data='set_age')
        ],
        [
            InlineKeyboardButton("⚖️ Вес", callback_data='set_weight'),
            InlineKeyboardButton("📏 Рост", callback_data='set_height')
        ],
        [InlineKeyboardButton("🔙 Назад", callback_data='settings')]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_training_settings_menu():
    keyboard = [
        [InlineKeyboardButton("💪 Тип тренировок", callback_data='set_training_type')],
        [InlineKeyboardButton("🔙 Назад", callback_data='settings')]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_ai_assistant_menu():
    keyboard = [
        [InlineKeyboardButton("💬 Получить общую консультацию у AI-консультанта", callback_data='set_training_type')],
        [InlineKeyboardButton("🍴 Расписать диету", callback_data='set_training_type')],
        [InlineKeyboardButton("📈 Разработать план тренировок", callback_data='set_training_type')],
        [InlineKeyboardButton("🔙 Назад", callback_data='settings')]
    ]
    return InlineKeyboardMarkup(keyboard)