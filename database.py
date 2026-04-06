from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Boolean, BigInteger, Text, DateTime
from datetime import datetime
from config import DATABASE_URL


# Принудительно заменяем схему на asyncpg если вдруг указан просто postgresql://
def _fix_url(url: str) -> str:
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


engine = create_async_engine(_fix_url(DATABASE_URL), echo=False)
async_session = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class DeletedMessage(Base):
    __tablename__ = "deleted_messages"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    business_connection_id: Mapped[str] = mapped_column(String(100))
    chat_id: Mapped[int] = mapped_column(BigInteger)
    message_id: Mapped[int] = mapped_column(BigInteger)
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    caption: Mapped[str | None] = mapped_column(Text, nullable=True)
    from_user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    from_user_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    deleted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class TranslatorSettings(Base):
    __tablename__ = "translator_settings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    chat_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    # язык собеседника -> на какой переводить тебе
    partner_lang: Mapped[str] = mapped_column(String(10), default="en")
    # твой язык -> на какой переводить собеседнику
    owner_lang: Mapped[str] = mapped_column(String(10), default="ru")


class KnownChat(Base):
    __tablename__ = "known_chats"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    chat_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    business_connection_id: Mapped[str] = mapped_column(String(100))
    last_seen: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class MessageCache(Base):
    __tablename__ = "message_cache"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    business_connection_id: Mapped[str] = mapped_column(String(100))
    chat_id: Mapped[int] = mapped_column(BigInteger)
    message_id: Mapped[int] = mapped_column(BigInteger)
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    caption: Mapped[str | None] = mapped_column(Text, nullable=True)
    from_user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    from_user_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncSession:
    async with async_session() as session:
        yield session
