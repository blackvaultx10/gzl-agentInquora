from __future__ import annotations

from typing import AsyncGenerator

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import BASE_DIR

DATABASE_URL = f"sqlite+aiosqlite:///{BASE_DIR}/inquora.db"
SYNC_DATABASE_URL = f"sqlite:///{BASE_DIR}/inquora.db"

engine = create_async_engine(DATABASE_URL, echo=False)
async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

sync_engine = create_engine(SYNC_DATABASE_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=sync_engine)

Base = declarative_base()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """?????????????"""
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()


def init_db() -> None:
    """????????"""
    from app.models_db import InquiryProject, ProviderConfig

    Base.metadata.create_all(bind=sync_engine)
