import os
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import MetaData

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL не найден в переменных окружения или файле .env")

# Настройка асинхронного движка PostgreSQL
engine = create_async_engine(DATABASE_URL, echo=True)

# Фабрика сессий
async_session = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# Переопределяем метаданные, чтобы SQLAlchemy искала таблицы только в нашей изолированной схеме
metadata = MetaData(schema="user_schema")
Base = declarative_base(metadata=metadata)

# Зависимость для FastAPI эндпоинтов
async def get_db():
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()