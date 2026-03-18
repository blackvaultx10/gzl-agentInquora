from __future__ import annotations

from pathlib import Path
from typing import AsyncGenerator

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import BASE_DIR

# 数据库路径
DATABASE_URL = f"sqlite+aiosqlite:///{BASE_DIR}/inquora.db"
SYNC_DATABASE_URL = f"sqlite:///{BASE_DIR}/inquora.db"

# 创建异步引擎
engine = create_async_engine(DATABASE_URL, echo=False)
async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# 创建同步引擎（用于初始化）
sync_engine = create_engine(SYNC_DATABASE_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=sync_engine)

Base = declarative_base()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """获取数据库会话的依赖函数。"""
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()


def init_db() -> None:
    """初始化数据库表。"""
    # 导入模型确保表被创建
    from app.models_db import ProviderConfig
    Base.metadata.create_all(bind=sync_engine)
