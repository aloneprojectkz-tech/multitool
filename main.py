import asyncio
import logging
import os
from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.types import BusinessConnection
from config import BOT_TOKEN
from database import init_db
from handlers import menu, deleted_messages, ai_assistant, translator, ai_settings

logging.basicConfig(level=logging.INFO)


async def main():
    await init_db()

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher()

    # Автоматически сохраняем business_connection_id при подключении
    @dp.business_connection()
    async def on_business_connect(bc: BusinessConnection):
        os.environ["BUSINESS_CONNECTION_ID"] = bc.id
        logging.info(f"Business connection: {bc.id}")

    dp.include_router(menu.router)
    dp.include_router(deleted_messages.router)
    dp.include_router(ai_assistant.router)
    dp.include_router(ai_settings.router)
    dp.include_router(translator.router)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
