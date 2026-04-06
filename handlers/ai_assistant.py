from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select
from database import async_session, KnownChat
from services.ai_service import ask_ai
from config import OWNER_ID

router = Router()

# { user_id: {"answer": str} }
_last_ai: dict[int, dict] = {}


class AIState(StatesGroup):
    waiting_prompt = State()


@router.message(F.text == "🤖 ИИ Ассистент", F.from_user.id == OWNER_ID)
async def ai_menu(message: Message, state: FSMContext):
    await state.set_state(AIState.waiting_prompt)
    await message.answer(
        "Введи запрос для ИИ:",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="❌ Отмена")]],
            resize_keyboard=True,
        ),
    )


@router.message(AIState.waiting_prompt, F.from_user.id == OWNER_ID)
async def process_ai_prompt(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        from handlers.menu import get_main_kb
        await message.answer("Отменено.", reply_markup=get_main_kb())
        return

    await message.answer("⏳ Думаю...")
    answer = await ask_ai(message.text)
    _last_ai[message.from_user.id] = {"answer": answer}

    # Строим инлайн-кнопки из известных чатов
    kb = await _build_chats_kb()
    await message.answer(
        f"💬 <b>Ответ ИИ:</b>\n\n{answer}\n\n<i>Выбери кому отправить или отмени:</i>",
        reply_markup=kb,
    )
    await state.clear()


async def _build_chats_kb() -> InlineKeyboardMarkup:
    async with async_session() as session:
        result = await session.execute(
            select(KnownChat).order_by(KnownChat.last_seen.desc()).limit(20)
        )
        chats = result.scalars().all()

    buttons = []
    for chat in chats:
        name = chat.chat_name or str(chat.chat_id)
        buttons.append([InlineKeyboardButton(
            text=f"📤 {name}",
            callback_data=f"ai_send_{chat.chat_id}",
        )])

    if not buttons:
        buttons.append([InlineKeyboardButton(
            text="⚠️ Нет известных чатов",
            callback_data="ai_no_chats",
        )])

    buttons.append([InlineKeyboardButton(text="❌ Не отправлять", callback_data="ai_cancel")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.callback_query(F.data.startswith("ai_send_"))
async def ai_do_send(callback: CallbackQuery, bot: Bot):
    target_chat_id = int(callback.data.replace("ai_send_", ""))
    answer = _last_ai.get(callback.from_user.id, {}).get("answer")

    if not answer:
        await callback.message.answer("Нет сохранённого ответа.")
        await callback.answer()
        return

    # Берём bc_id из БД
    async with async_session() as session:
        result = await session.execute(
            select(KnownChat).where(KnownChat.chat_id == target_chat_id)
        )
        chat = result.scalar_one_or_none()

    if not chat:
        await callback.message.answer("❌ Чат не найден в БД.")
        await callback.answer()
        return

    try:
        await bot.send_message(
            chat_id=target_chat_id,
            text=answer,
            business_connection_id=chat.business_connection_id,
        )
        await callback.message.edit_reply_markup(reply_markup=None)
        from handlers.menu import get_main_kb
        await callback.message.answer("✅ Отправлено!", reply_markup=get_main_kb())
    except Exception as e:
        await callback.message.answer(f"❌ Ошибка: {e}")

    await callback.answer()


@router.callback_query(F.data == "ai_cancel")
async def ai_cancel(callback: CallbackQuery):
    await callback.message.edit_reply_markup(reply_markup=None)
    from handlers.menu import get_main_kb
    await callback.message.answer("Окей.", reply_markup=get_main_kb())
    await callback.answer()


@router.callback_query(F.data == "ai_no_chats")
async def ai_no_chats(callback: CallbackQuery):
    await callback.answer("Пока нет ни одного чата. Дождись сообщения от собеседника.", show_alert=True)
