from dotenv import load_dotenv
import os

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:hFvbdReLMuQIpCBtrAdCFItUVPoIAotH@postgres-vmng.railway.internal:5432/railway"
)
# Твой личный Telegram user_id (владелец бота)
OWNER_ID = int(os.getenv("OWNER_ID", "0"))
