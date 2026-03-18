from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes_config import router as config_router
from app.api.routes_inquiry import router as inquiry_router
from app.api.routes_ws import router as ws_router
from app.config import get_settings
from app.db import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理。"""
    # 启动时初始化数据库
    init_db()
    yield
    # 关闭时清理资源


settings = get_settings()
app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(inquiry_router, prefix=settings.api_prefix)
app.include_router(config_router, prefix=settings.api_prefix)
app.include_router(ws_router)  # WebSocket不需要前缀


@app.get("/health")
async def healthcheck() -> dict[str, str]:
    return {"status": "ok"}

