# bot/ai_assistant/open_ai_bot.py
"""
Это класс бота OpenAI. Он наследуется от базового класса бота и обеспечивает реализацию бота OpenAI.
Он использует API OpenAI для генерации ответов на запросы пользователей.
"""

import asyncio
import os
from os import environ
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.storage.memory import MemoryStorage
from openai import OpenAI

# Настройки
OPENAI_API_KEY = environ.get('OPENAI_API_KEY')
TELEGRAM_TOKEN = environ.get('TELEGRAM_TOKEN')
MODEL = 'gpt-3.5-turbo'

client = OpenAI(api_key=OPENAI_API_KEY)

# Состояния FSM
class ChatState(StatesGroup):
    chatting = State() # Состояние диалога с пользователем в чате

# Хранение истории разговоров (user_id: list of messages)
conversations = {}

# Инициализация бота
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher(bot, storage=MemoryStorage())

@dp.message(Command('start'))
async def start(message: types.Message):
    """Команда /start: Отправка сообщения с inline-кнопкой"""
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="Начать чат с ChatGPT", callback_data="start_chat")]
    ])
    await message.answer("Привет! Нажми кнопку, чтобы начать взаимодействие с ChatGPT.", reply_markup=keyboard)

@dp.callback_query(lambda c: c.data == 'start_chat')
async def start_chat_callback(callback: types.CallbackQuery, state: FSMContext):
    """Обработка нажатия inline-кнопки"""
    await callback.answer("Чат с ChatGPT начат! Отправляй сообщения.")
    await state.set_state(ChatState.chatting)

    user_id = callback.from_user.id
    conversations[user_id] = []  # Инициализация истории для пользователя

    await callback.message.answer("ChatGPT готов. Что вы хотите спросить?")

@dp.message(ChatState.chatting)
async def handle_message(message: types.Message, state: FSMContext):
    """Обработка сообщений в состоянии chatting"""
    user_id = message.from_user.id
    user_message = message.text

    # Добавляем сообщение пользователя в историю
    if user_id not in conversations:
        conversations[user_id] = []
    conversations[user_id].append({"role": "user", "content": user_message})

    # Вызов OpenAI API
    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "system", "content": "You are a helpful assistant."}] + conversations[user_id]
        )
        ai_response = response.choices[0].message.content

        # Добавляем ответ AI в историю
        conversations[user_id].append({"role": "assistant", "content": ai_response})

        # Отправляем ответ пользователю
        await message.answer(ai_response)
    except Exception as e:
        await message.answer(f"Ошибка: {str(e)}")

@dp.message(Command('stop'))
async def stop_chat(message: types.Message, state: FSMContext):
    """Команда /stop для выхода из чата"""
    await state.clear()
    user_id = message.from_user.id
    if user_id in conversations:
        del conversations[user_id]  # Очистка истории
    await message.answer("Чат с ChatGPT завершён. Используй /start для начала.")

# Запуск бота
async def main():
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())