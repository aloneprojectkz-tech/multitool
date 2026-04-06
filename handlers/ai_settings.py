from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select, delete, func
from database import async_session, AISettings, AIHistory, KnownChat
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


def _main_kb(auto: str, prompt_preview: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🤖 Автоответ: {auto}", callback_data="ais_toggle_auto")],
        [InlineKeyboardButton(text="✏️ Изменить промпт", callback_data="ais_edit_prompt")],
        [InlineKeyboardButton(text="🔄 Сбросить промпт", callback_data="ais_reset_prompt")],
        [InlineKeyboardButton(text="🧠 Память собеседников", callback_data="ais_memory")],
    ])


def _main_text(auto: str, prompt_preview: str) -> str:
    return (
        f"⚙️ <b>Настройки ИИ</b>\n\n"
        f"🤖 Автоответ: <b>{auto}</b>\n\n"
        f"📝 Текущий промпт:\n<blockquote>{prompt_preview}</blockquote>"
    )


@router.message(F.text == "⚙️ Настройки ИИ", F.from_user.id == OWNER_ID)
async def ai_settings_menu(message: Message):
    s = await get_ai_settings()
    auto = "✅ Включён" if s.auto_reply_enabled else "❌ Выключен"
    preview = s.system_prompt[:100] + "..." if len(s.system_prompt) > 100 else s.system_prompt
    await message.answer(_main_text(auto, preview), reply_markup=_main_kb(auto, preview))


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

    s2 = await get_ai_settings()
    auto = "✅ Включён" if s2.auto_reply_enabled else "❌ Выключен"
    preview = s2.system_prompt[:100] + "..." if len(s2.system_prompt) > 100 else s2.system_prompt
    await callback.message.edit_text(_main_text(auto, preview), reply_markup=_main_kb(auto, preview))
    await callback.answer()


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


# ─── Память ──────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "ais_memory")
async def memory_list(callback: CallbackQuery):
    async with async_session() as session:
        # Чаты у которых есть история
        result = await session.execute(
            select(KnownChat).join(
                AIHistory, KnownChat.chat_id == AIHistory.chat_id
            ).distinct()
        )
        chats = result.scalars().all()

        # Считаем сообщения для каждого
        counts = {}
        for chat in chats:
            cnt = await session.execute(
                select(func.count()).where(AIHistory.chat_id == chat.chat_id)
            )
            counts[chat.chat_id] = cnt.scalar()

    if not chats:
        await callback.answer("Память пуста — ни одного диалога.", show_alert=True)
        return

    buttons = [
        [InlineKeyboardButton(
            text=f"🧠 {chat.chat_name or chat.chat_id} ({counts.get(chat.chat_id, 0)} сообщ.)",
            callback_data=f"ais_mem_{chat.chat_id}",
        )]
        for chat in chats
    ]
    buttons.append([InlineKeyboardButton(text="🗑 Очистить всю память", callback_data="ais_mem_clear_all")])
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="ais_back")])

    await callback.message.edit_text(
        "🧠 <b>Память ИИ по собеседникам:</b>\n\nВыбери чат чтобы очистить его историю:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("ais_mem_") & ~F.data.startswith("ais_mem_clear"))
async def memory_chat_actions(callback: CallbackQuery):
    chat_id = int(callback.data.replace("ais_mem_", ""))

    async with async_session() as session:
        result = await session.execute(
            select(KnownChat).where(KnownChat.chat_id == chat_id)
        )
        chat = result.scalar_one_or_none()
        cnt = await session.execute(
            select(func.count()).where(AIHistory.chat_id == chat_id)
        )
        count = cnt.scalar()

    name = chat.chat_name if chat else str(chat_id)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗑 Очистить память", callback_data=f"ais_mem_clear_{chat_id}")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="ais_memory")],
    ])
    await callback.message.edit_text(
        f"🧠 <b>{name}</b>\n\nСообщений в памяти: <b>{count}</b>",
        reply_markup=kb,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("ais_mem_clear_"))
async def memory_clear_one(callback: CallbackQuery):
    chat_id = int(callback.data.replace("ais_mem_clear_", ""))
    async with async_session() as session:
        await session.execute(delete(AIHistory).where(AIHistory.chat_id == chat_id))
        await session.commit()
    await callback.answer("✅ Память очищена.", show_alert=True)
    await memory_list(callback)


@router.callback_query(F.data == "ais_mem_clear_all")
async def memory_clear_all(callback: CallbackQuery):
    async with async_session() as session:
        await session.execute(delete(AIHistory))
        await session.commit()
    await callback.answer("✅ Вся память очищена.", show_alert=True)
    s = await get_ai_settings()
    auto = "✅ Включён" if s.auto_reply_enabled else "❌ Выключен"
    preview = s.system_prompt[:100] + "..." if len(s.system_prompt) > 100 else s.system_prompt
    await callback.message.edit_text(_main_text(auto, preview), reply_markup=_main_kb(auto, preview))


@router.callback_query(F.data == "ais_back")
async def ais_back(callback: CallbackQuery):
    s = await get_ai_settings()
    auto = "✅ Включён" if s.auto_reply_enabled else "❌ Выключен"
    preview = s.system_prompt[:100] + "..." if len(s.system_prompt) > 100 else s.system_prompt
    await callback.message.edit_text(_main_text(auto, preview), reply_markup=_main_kb(auto, preview))
    await callback.answer()
