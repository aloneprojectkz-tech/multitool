from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select
from database import async_session, AISettings
from config import OWNER_ID

router = Router()

DEFAULT_PROMPT = "Ты полезный ассистент. Отвечай чётко и по делу."


class AISettingsState(StatesGroup):
    waiting_prompt = State()


async def get_ai_settings() -> AISettings:
    async with async_session() as session:
        result = await session.execute(select(AISettings))
        settings = result.scalar_one_or_none()
        if not settings:
            settings = AISettings(system_prompt=DEFAULT_PROMPT, auto_reply_enabled=False)
            session.add(settings)
            await session.commit()
            await session.refresh(settings)
        return settings


@router.message(F.text == "⚙️ Настройки ИИ", F.from_user.id == OWNER_ID)
async def ai_settings_menu(message: Message):
    await _show_settings(message)


async def _show_settings(message: Message):
    s = await get_ai_settings()
    auto = "✅ Включён" if s.auto_reply_enabled else "❌ Выключен"
    prompt_preview = s.system_prompt[:100] + "..." if len(s.system_prompt) > 100 else s.system_prompt

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🤖 Автоответ: {auto}", callback_data="ais_toggle_auto")],
        [InlineKeyboardButton(text="✏️ Изменить промпт", callback_data="ais_edit_prompt")],
        [InlineKeyboardButton(text="🔄 Сбросить промпт", callback_data="ais_reset_prompt")],
    ])
    await message.answer(
        f"⚙️ <b>Настройки ИИ</b>\n\n"
        f"🤖 Автоответ: <b>{auto}</b>\n\n"
        f"📝 Текущий промпт:\n<blockquote>{prompt_preview}</blockquote>",
        reply_markup=kb,
    )


@router.callback_query(F.data == "ais_toggle_auto")
async def toggle_auto_reply(callback: CallbackQuery):
    async with async_session() as session:
        result = await session.execute(select(AISettings))
        s = result.scalar_one_or_none()
        if not s:
            s = AISettings(system_prompt=DEFAULT_PROMPT, auto_reply_enabled=False)
            session.add(s)
        s.auto_reply_enabled = not s.auto_reply_enabled
        await session.commit()
        status = "включён ✅" if s.auto_reply_enabled else "выключен ❌"

    await callback.answer(f"Автоответ {status}", show_alert=True)
    # Обновляем сообщение
    s2 = await get_ai_settings()
    auto = "✅ Включён" if s2.auto_reply_enabled else "❌ Выключен"
    prompt_preview = s2.system_prompt[:100] + "..." if len(s2.system_prompt) > 100 else s2.system_prompt
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🤖 Автоответ: {auto}", callback_data="ais_toggle_auto")],
        [InlineKeyboardButton(text="✏️ Изменить промпт", callback_data="ais_edit_prompt")],
        [InlineKeyboardButton(text="🔄 Сбросить промпт", callback_data="ais_reset_prompt")],
    ])
    await callback.message.edit_text(
        f"⚙️ <b>Настройки ИИ</b>\n\n"
        f"🤖 Автоответ: <b>{auto}</b>\n\n"
        f"📝 Текущий промпт:\n<blockquote>{prompt_preview}</blockquote>",
        reply_markup=kb,
    )


@router.callback_query(F.data == "ais_edit_prompt")
async def edit_prompt_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer(
        "Введи новый системный промпт для ИИ:\n\n"
        "<i>Например: Ты менеджер по продажам. Отвечай вежливо и предлагай товары.</i>",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="❌ Отмена")]],
            resize_keyboard=True,
        ),
    )
    await state.set_state(AISettingsState.waiting_prompt)
    await callback.answer()


@router.message(AISettingsState.waiting_prompt, F.from_user.id == OWNER_ID)
async def save_prompt(message: Message, state: FSMContext):
    from handlers.menu import get_main_kb
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=get_main_kb())
        return

    async with async_session() as session:
        result = await session.execute(select(AISettings))
        s = result.scalar_one_or_none()
        if not s:
            s = AISettings(system_prompt=message.text, auto_reply_enabled=False)
            session.add(s)
        else:
            s.system_prompt = message.text
        await session.commit()

    await state.clear()
    await message.answer("✅ Промпт сохранён!", reply_markup=get_main_kb())


@router.callback_query(F.data == "ais_reset_prompt")
async def reset_prompt(callback: CallbackQuery):
    async with async_session() as session:
        result = await session.execute(select(AISettings))
        s = result.scalar_one_or_none()
        if s:
            s.system_prompt = DEFAULT_PROMPT
            await session.commit()
    await callback.answer("Промпт сброшен до стандартного.", show_alert=True)
