from aiogram import Router, Bot
from aiogram.types import BusinessMessagesDeleted, Message
from sqlalchemy import select
from database import async_session, MessageCache, DeletedMessage
from config import OWNER_ID
from datetime import datetime

router = Router()


# Кэшируем все входящие бизнес-сообщения
@router.business_message()
async def cache_message(message: Message):
    async with async_session() as session:
        # Удаляем старый кэш если есть
        existing = await session.execute(
            select(MessageCache).where(
                MessageCache.business_connection_id == message.business_connection_id,
                MessageCache.chat_id == message.chat.id,
                MessageCache.message_id == message.message_id,
            )
        )
        existing = existing.scalar_one_or_none()
        if not existing:
            cached = MessageCache(
                business_connection_id=message.business_connection_id,
                chat_id=message.chat.id,
                message_id=message.message_id,
                text=message.text,
                caption=message.caption,
                from_user_id=message.from_user.id if message.from_user else None,
                from_user_name=(
                    message.from_user.full_name if message.from_user else None
                ),
            )
            session.add(cached)
            await session.commit()


@router.deleted_business_messages()
async def on_deleted_messages(event: BusinessMessagesDeleted, bot: Bot):
    async with async_session() as session:
        for msg_id in event.message_ids:
            # Ищем в кэше
            result = await session.execute(
                select(MessageCache).where(
                    MessageCache.business_connection_id == event.business_connection_id,
                    MessageCache.chat_id == event.chat.id,
                    MessageCache.message_id == msg_id,
                )
            )
            cached: MessageCache | None = result.scalar_one_or_none()

            text = cached.text or cached.caption if cached else None
            sender = cached.from_user_name if cached else "Неизвестно"

            # Сохраняем в deleted_messages
            deleted = DeletedMessage(
                business_connection_id=event.business_connection_id,
                chat_id=event.chat.id,
                message_id=msg_id,
                text=text,
                from_user_id=cached.from_user_id if cached else None,
                from_user_name=sender,
                deleted_at=datetime.utcnow(),
            )
            session.add(deleted)

            # Уведомляем владельца
            chat_link = f"tg://user?id={event.chat.id}"
            notify_text = (
                f"🗑 <b>Удалено сообщение</b>\n"
                f"👤 От: <b>{sender}</b> (<a href='{chat_link}'>чат</a>)\n"
                f"🆔 ID сообщения: <code>{msg_id}</code>\n"
            )
            if text:
                notify_text += f"\n📝 <b>Текст:</b>\n<blockquote>{text}</blockquote>"
            else:
                notify_text += "\n📎 <i>(медиа без текста или текст не был закэширован)</i>"

            await bot.send_message(OWNER_ID, notify_text)

        await session.commit()
