from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from services.ai_service import ask_ai
from config import OWNER_ID

router = Router()

# { user_id: {"answer": str, "bc_id": str, "chat_id": int} }
_last_ai: dict[int, dict] = {}

# Сохраняем последний известный business_connection_id
_bc_id: str = ""


class AIState(StatesGroup):
    waiting_prompt = State()
    waiting_send_target = State()


# Перехватываем любое business_message чтобы запомнить bc_id
@router.business_message()
async def remember_bc_id(message: Message):
    global _bc_id
    if message.business_connection_id:
        _bc_id = message.business_connection_id


@router.message(F.text == "🤖 ИИ Ассистент", F.from_user.id == OWNER_ID)
async def ai_menu(message: Message, state: FSMContext):
    await state.set_state(AIState.waiting_prompt)
    await message.answer(
        "Введи запрос для ИИ. Я отвечу и предложу отправить ответ собеседнику.",
        reply_markup=cancel_kb(),
    )


@router.message(AIState.waiting_prompt, F.from_user.id == OWNER_ID)
async def process_ai_prompt(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=main_kb())
        return

    await message.answer("⏳ Думаю...")
    answer = await ask_ai(message.text)
    _last_ai[message.from_user.id] = {"answer": answer}

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📤 Отправить собеседнику", callback_data="ai_send")],
        [InlineKeyboardButton(text="❌ Не отправлять", callback_data="ai_cancel")],
    ])
    await message.answer(f"💬 <b>Ответ ИИ:</b>\n\n{answer}", reply_markup=kb)
    await state.clear()


@router.callback_query(F.data == "ai_send")
async def ai_send_ask(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer(
        "Перешли сообщение от нужного собеседника или введи его <b>chat_id</b>:",
        reply_markup=cancel_kb(),
    )
    await state.set_state(AIState.waiting_send_target)
    await callback.answer()


@router.message(AIState.waiting_send_target, F.from_user.id == OWNER_ID)
async def ai_do_send(message: Message, state: FSMContext, bot: Bot):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=main_kb())
        return

    target_chat_id = None
    if message.forward_from:
        target_chat_id = message.forward_from.id
    elif message.text and message.text.lstrip("-").isdigit():
        target_chat_id = int(message.text)

    if not target_chat_id:
        await message.answer("Не смог определить chat_id. Попробуй ещё раз.")
        return

    answer = _last_ai.get(message.from_user.id, {}).get("answer")
    if not answer:
        await message.answer("Нет сохранённого ответа ИИ.")
        await state.clear()
        return

    if not _bc_id:
        await message.answer(
            "❌ business_connection_id ещё не известен. "
            "Дождись любого сообщения от собеседника через бизнес-аккаунт."
        )
        await state.clear()
        return

    try:
        await bot.send_message(
            chat_id=target_chat_id,
            text=answer,
            business_connection_id=_bc_id,
        )
        await message.answer("✅ Отправлено!", reply_markup=main_kb())
    except Exception as e:
        await message.answer(f"❌ Ошибка отправки: {e}", reply_markup=main_kb())

    await state.clear()


@router.callback_query(F.data == "ai_cancel")
async def ai_cancel(callback: CallbackQuery):
    await callback.message.answer("Окей, не отправляем.", reply_markup=main_kb())
    await callback.answer()


def main_kb():
    from handlers.menu import get_main_kb
    return get_main_kb()


def cancel_kb():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Отмена")]],
        resize_keyboard=True,
    )
