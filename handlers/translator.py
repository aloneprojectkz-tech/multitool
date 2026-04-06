from aiogram import Router, F, Bot
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton,
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select, delete
from database import async_session, TranslatorSettings
from services.translator_service import translate
from config import OWNER_ID

router = Router()

LANGUAGES = {
    "en": "🇬🇧 Английский",
    "ru": "🇷🇺 Русский",
    "de": "🇩🇪 Немецкий",
    "fr": "🇫🇷 Французский",
    "es": "🇪🇸 Испанский",
    "zh-CN": "🇨🇳 Китайский",
    "ar": "🇸🇦 Арабский",
    "tr": "🇹🇷 Турецкий",
    "uk": "🇺🇦 Украинский",
}


class TranslatorState(StatesGroup):
    waiting_chat_id = State()
    waiting_partner_lang = State()
    waiting_owner_lang = State()


# ─── Меню переводчика ────────────────────────────────────────────────────────

@router.message(F.text == "🌐 Переводчик", F.from_user.id == OWNER_ID)
async def translator_menu(message: Message):
    async with async_session() as session:
        result = await session.execute(select(TranslatorSettings))
        settings = result.scalars().all()

    if not settings:
        text = "📋 Список переводчиков пуст."
    else:
        lines = []
        for s in settings:
            status = "✅" if s.enabled else "⏸"
            lines.append(
                f"{status} <b>{s.chat_name or s.chat_id}</b> "
                f"(ID: <code>{s.chat_id}</code>) | "
                f"Они→{s.partner_lang.upper()} | Ты→{s.owner_lang.upper()}"
            )
        text = "🌐 <b>Активные переводчики:</b>\n\n" + "\n".join(lines)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить чат", callback_data="tr_add")],
        [InlineKeyboardButton(text="🗑 Удалить чат", callback_data="tr_remove")],
        [InlineKeyboardButton(text="🔄 Вкл/Выкл", callback_data="tr_toggle")],
    ])
    await message.answer(text, reply_markup=kb)


# ─── Добавить чат ────────────────────────────────────────────────────────────

@router.callback_query(F.data == "tr_add")
async def tr_add_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer(
        "Введи <b>chat_id</b> собеседника или перешли его сообщение:",
        reply_markup=cancel_kb(),
    )
    await state.set_state(TranslatorState.waiting_chat_id)
    await callback.answer()


@router.message(TranslatorState.waiting_chat_id, F.from_user.id == OWNER_ID)
async def tr_got_chat_id(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=main_kb())
        return

    chat_id = None
    chat_name = None

    if message.forward_from:
        chat_id = message.forward_from.id
        chat_name = message.forward_from.full_name
    elif message.text and message.text.lstrip("-").isdigit():
        chat_id = int(message.text)

    if not chat_id:
        await message.answer("Не смог определить chat_id. Попробуй ещё раз.")
        return

    await state.update_data(chat_id=chat_id, chat_name=chat_name)
    await message.answer(
        "Выбери язык <b>собеседника</b> (с какого переводить тебе):",
        reply_markup=lang_kb("partner"),
    )
    await state.set_state(TranslatorState.waiting_partner_lang)


@router.callback_query(TranslatorState.waiting_partner_lang, F.data.startswith("lang_partner_"))
async def tr_got_partner_lang(callback: CallbackQuery, state: FSMContext):
    lang = callback.data.replace("lang_partner_", "")
    await state.update_data(partner_lang=lang)
    await callback.message.answer(
        "Выбери <b>твой язык</b> (на какой переводить собеседнику):",
        reply_markup=lang_kb("owner"),
    )
    await state.set_state(TranslatorState.waiting_owner_lang)
    await callback.answer()


@router.callback_query(TranslatorState.waiting_owner_lang, F.data.startswith("lang_owner_"))
async def tr_got_owner_lang(callback: CallbackQuery, state: FSMContext):
    lang = callback.data.replace("lang_owner_", "")
    data = await state.get_data()

    async with async_session() as session:
        existing = await session.execute(
            select(TranslatorSettings).where(TranslatorSettings.chat_id == data["chat_id"])
        )
        existing = existing.scalar_one_or_none()
        if existing:
            existing.partner_lang = data["partner_lang"]
            existing.owner_lang = lang
            existing.enabled = True
            existing.chat_name = data.get("chat_name") or existing.chat_name
        else:
            session.add(TranslatorSettings(
                chat_id=data["chat_id"],
                chat_name=data.get("chat_name"),
                partner_lang=data["partner_lang"],
                owner_lang=lang,
                enabled=True,
            ))
        await session.commit()

    await callback.message.answer(
        f"✅ Переводчик добавлен для чата <code>{data['chat_id']}</code>",
        reply_markup=main_kb(),
    )
    await state.clear()
    await callback.answer()


# ─── Удалить чат ─────────────────────────────────────────────────────────────

@router.callback_query(F.data == "tr_remove")
async def tr_remove(callback: CallbackQuery):
    async with async_session() as session:
        result = await session.execute(select(TranslatorSettings))
        settings = result.scalars().all()

    if not settings:
        await callback.message.answer("Список пуст.")
        await callback.answer()
        return

    buttons = [
        [InlineKeyboardButton(
            text=f"🗑 {s.chat_name or s.chat_id}",
            callback_data=f"tr_del_{s.chat_id}"
        )]
        for s in settings
    ]
    await callback.message.answer(
        "Выбери чат для удаления:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("tr_del_"))
async def tr_do_remove(callback: CallbackQuery):
    chat_id = int(callback.data.replace("tr_del_", ""))
    async with async_session() as session:
        await session.execute(
            delete(TranslatorSettings).where(TranslatorSettings.chat_id == chat_id)
        )
        await session.commit()
    await callback.message.answer(f"✅ Удалено для чата <code>{chat_id}</code>", reply_markup=main_kb())
    await callback.answer()


# ─── Вкл/Выкл ────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "tr_toggle")
async def tr_toggle_list(callback: CallbackQuery):
    async with async_session() as session:
        result = await session.execute(select(TranslatorSettings))
        settings = result.scalars().all()

    if not settings:
        await callback.message.answer("Список пуст.")
        await callback.answer()
        return

    buttons = [
        [InlineKeyboardButton(
            text=f"{'✅' if s.enabled else '⏸'} {s.chat_name or s.chat_id}",
            callback_data=f"tr_tog_{s.chat_id}"
        )]
        for s in settings
    ]
    await callback.message.answer(
        "Выбери чат для переключения:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("tr_tog_"))
async def tr_do_toggle(callback: CallbackQuery):
    chat_id = int(callback.data.replace("tr_tog_", ""))
    async with async_session() as session:
        result = await session.execute(
            select(TranslatorSettings).where(TranslatorSettings.chat_id == chat_id)
        )
        s = result.scalar_one_or_none()
        if s:
            s.enabled = not s.enabled
            await session.commit()
            status = "включён ✅" if s.enabled else "выключен ⏸"
            await callback.message.answer(f"Переводчик {status} для <code>{chat_id}</code>", reply_markup=main_kb())
    await callback.answer()


# ─── Перехват бизнес-сообщений для перевода ──────────────────────────────────

@router.business_message(F.from_user.id != OWNER_ID)
async def translate_incoming(message: Message, bot: Bot):
    """Переводим входящее сообщение от собеседника владельцу."""
    async with async_session() as session:
        result = await session.execute(
            select(TranslatorSettings).where(
                TranslatorSettings.chat_id == message.from_user.id,
                TranslatorSettings.enabled == True,
            )
        )
        settings: TranslatorSettings | None = result.scalar_one_or_none()

    if not settings:
        return

    original = message.text or message.caption
    if not original:
        return

    translated = translate(original, source=settings.partner_lang, target="ru")

    await bot.send_message(
        OWNER_ID,
        f"📨 <b>Сообщение от {message.from_user.full_name}</b>:\n\n"
        f"🔤 <b>Оригинал:</b>\n<blockquote>{original}</blockquote>\n\n"
        f"🇷🇺 <b>Перевод:</b>\n<blockquote>{translated}</blockquote>",
    )


@router.business_message(F.from_user.id == OWNER_ID)
async def translate_outgoing(message: Message, bot: Bot):
    """Переводим исходящее сообщение владельца собеседнику."""
    # chat.id — это собеседник в бизнес-чате
    target_chat_id = message.chat.id
    if target_chat_id == OWNER_ID:
        return  # сам себе не переводим

    async with async_session() as session:
        result = await session.execute(
            select(TranslatorSettings).where(
                TranslatorSettings.chat_id == target_chat_id,
                TranslatorSettings.enabled == True,
            )
        )
        settings: TranslatorSettings | None = result.scalar_one_or_none()

    if not settings:
        return

    original = message.text or message.caption
    if not original:
        return

    translated = translate(original, source="ru", target=settings.owner_lang)

    # Отправляем перевод собеседнику через бизнес-соединение
    try:
        await bot.send_message(
            chat_id=target_chat_id,
            text=translated,
            business_connection_id=message.business_connection_id,
        )
    except Exception as e:
        await bot.send_message(OWNER_ID, f"❌ Ошибка отправки перевода: {e}")


# ─── Вспомогательные клавиатуры ──────────────────────────────────────────────

def lang_kb(prefix: str) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=name, callback_data=f"lang_{prefix}_{code}")]
        for code, name in LANGUAGES.items()
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def cancel_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Отмена")]],
        resize_keyboard=True,
    )


def main_kb():
    from handlers.menu import get_main_kb
    return get_main_kb()
