from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import CommandStart
from config import OWNER_ID

router = Router()


def get_main_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🤖 ИИ Ассистент"), KeyboardButton(text="⚙️ Настройки ИИ")],
            [KeyboardButton(text="🌐 Переводчик")],
            [KeyboardButton(text="🗑 Удалённые сообщения")],
        ],
        resize_keyboard=True,
    )


@router.message(CommandStart(), F.from_user.id == OWNER_ID)
async def cmd_start(message: Message):
    await message.answer(
        "👋 Привет! Я твой бизнес-бот.\n\n"
        "Что умею:\n"
        "• 🗑 Уведомляю об удалённых сообщениях\n"
        "• 🤖 ИИ-ассистент с отправкой ответа собеседнику\n"
        "• 🌐 Переводчик для выбранных чатов\n",
        reply_markup=get_main_kb(),
    )


@router.message(F.text == "🗑 Удалённые сообщения", F.from_user.id == OWNER_ID)
async def deleted_info(message: Message):
    await message.answer(
        "Я автоматически уведомляю тебя когда собеседник удаляет сообщение. "
        "Ничего настраивать не нужно — просто жди уведомлений 👆"
    )


# Блокируем доступ посторонних
@router.message(~F.from_user.id.in_({OWNER_ID}))
async def block_others(message: Message):
    pass  # молча игнорируем
