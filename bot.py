import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.filters import Command
from datetime import datetime, timedelta
from config import BOT_TOKEN, INITIAL_PASSWORD, AUTOLOCK_TIMEOUT, UNLOCK_CODE
from mega_utils import upload_file, list_files, delete_file

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
logging.basicConfig(filename='log.txt', level=logging.INFO, format='%(asctime)s - %(message)s')

sessions = {}
upload_sessions = {}

class Auth(StatesGroup):
    waiting_password = State()
    active = State()
    waiting_file = State()
    waiting_delete = State()

def log(user_id, action):
    logging.info(f"[{user_id}] {action}")

def get_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1. База данных", callback_data="db")],
        [InlineKeyboardButton(text="2. Настройки", callback_data="settings")],
        [InlineKeyboardButton(text="3. Выход", callback_data="logout")]
    ])

def get_db_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Сохранить информацию", callback_data="save")],
        [InlineKeyboardButton(text="Просмотреть информацию", callback_data="view")]
    ])

def get_settings_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Сменить пароль", callback_data="nop")],
        [InlineKeyboardButton(text="Аварийное отключение", callback_data="lockdown")],
        [InlineKeyboardButton(text="Просмотр логов", callback_data="logs")]
    ])

@dp.message(Command("start"))
async def start(message: types.Message, state: FSMContext):
    await state.set_state(Auth.waiting_password)
    await message.answer("Введите пароль:")

@dp.message(Auth.waiting_password)
async def enter_password(message: types.Message, state: FSMContext):
    if message.text == INITIAL_PASSWORD or message.text == UNLOCK_CODE:
        await state.set_state(Auth.active)
        sessions[message.from_user.id] = datetime.now()
        await message.answer("Доступ разрешён.", reply_markup=get_menu())
        log(message.from_user.id, "Успешный вход")
    else:
        await message.answer("Неверный пароль.")
        log(message.from_user.id, "Неверный пароль")

@dp.callback_query(lambda c: True)
async def menu_handler(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    last = sessions.get(user_id)
    if not last or datetime.now() - last > timedelta(seconds=AUTOLOCK_TIMEOUT):
        await state.set_state(Auth.waiting_password)
        await callback.message.answer("Сессия завершена. Введите пароль:")
        log(user_id, "Автоблокировка")
        return
    sessions[user_id] = datetime.now()

    if callback.data == "db":
        await callback.message.edit_text("Раздел 'База данных':", reply_markup=get_db_menu())
    elif callback.data == "save":
        upload_sessions[user_id] = []
        await state.set_state(Auth.waiting_file)
        await callback.message.answer("Отправьте файлы. Когда закончите — напишите 'готово'.")
    elif callback.data == "view":
        files = list_files()
        if not files:
            await callback.message.answer("Файлы не найдены.")
            return
        msg = "\n".join([f"{i+1}. {f[0]}" for i, f in enumerate(files)])
        await state.set_state(Auth.waiting_delete)
        await callback.message.answer(f"Список файлов:\n{msg}\n\nЧтобы удалить — напишите номер.")
        sessions[user_id] = [(f[1], f[0]) for f in files]
    elif callback.data == "settings":
        await callback.message.edit_text("Настройки:", reply_markup=get_settings_menu())
    elif callback.data == "logout":
        await state.set_state(Auth.waiting_password)
        await callback.message.answer("Вы вышли. Введите пароль.")
        log(user_id, "Ручной выход")
    elif callback.data == "lockdown":
        await state.set_state(Auth.waiting_password)
        await callback.message.answer("Система заблокирована. Введите аварийный код.")
        log(user_id, "Аварийная блокировка")
    elif callback.data == "logs":
        with open("log.txt", "r") as f:
            text = f.read()[-4000:]
        await callback.message.answer(f"Логи:\n{text[-4000:]}")

@dp.message(Auth.waiting_file)
async def handle_files(message: types.Message, state: FSMContext):
    if message.text and message.text.lower() == "готово":
        await state.set_state(Auth.active)
        await message.answer("Загрузка завершена.", reply_markup=get_menu())
        log(message.from_user.id, "Закончил загрузку файлов")
        return
    if message.document:
        f = await message.bot.download(message.document)
        content = f.read()
        upload_file(content, message.document.file_name)
        await message.answer(f"Файл {message.document.file_name} сохранён.")
        log(message.from_user.id, f"Загрузил файл: {message.document.file_name}")
    elif message.photo:
        photo = message.photo[-1]
        f = await message.bot.download(photo)
        content = f.read()
        upload_file(content, f"photo_{photo.file_id}.jpg")
        await message.answer("Фото сохранено.")
        log(message.from_user.id, "Загрузил фото")
    elif message.audio:
        f = await message.bot.download(message.audio)
        content = f.read()
        upload_file(content, message.audio.file_name or "audio.mp3")
        await message.answer("Аудио сохранено.")
        log(message.from_user.id, "Загрузил аудио")
    else:
        await message.answer("Неподдерживаемый тип файла.")

@dp.message(Auth.waiting_delete)
async def handle_delete(message: types.Message, state: FSMContext):
    try:
        index = int(message.text.strip()) - 1
        file_id, name = sessions[message.from_user.id][index]
        delete_file(file_id)
        await message.answer(f"Файл '{name}' удалён.")
        log(message.from_user.id, f"Удалил файл {name}")
    except Exception:
        await message.answer("Ошибка. Укажите корректный номер файла.")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
