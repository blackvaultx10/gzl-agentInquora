from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import async_session_maker
from app.security import decrypt_value

if TYPE_CHECKING:
    pass


class ConfigManager:
    """配置管理器 - 从数据库获取动态配置。"""

    async def get_config(self, provider_type: str) -> dict | None:
        """获取指定提供商的配置。"""
        async with async_session_maker() as session:
            from app.models_db import ProviderConfig

            result = await session.execute(
                select(ProviderConfig).where(
                    ProviderConfig.provider_type == provider_type,
                    ProviderConfig.is_active == True
                )
            )
            config = result.scalar_one_or_none()

            if not config:
                return None

            return {
                "provider_type": config.provider_type,
                "name": config.name,
                "api_key": decrypt_value(config.api_key),
                "secret_key": decrypt_value(config.secret_key),
                "base_url": config.base_url,
                "model": config.model,
                "extra_config": config.extra_config,
            }

    async def get_llm_config(self) -> dict | None:
        """获取 LLM 配置（按优先级：DeepSeek > OpenAI）。"""
        # 优先尝试 DeepSeek
        config = await self.get_config("deepseek")
        if config and config.get("api_key"):
            return {**config, "provider": "deepseek"}

        # 其次尝试 OpenAI
        config = await self.get_config("openai")
        if config and config.get("api_key"):
            return {**config, "provider": "openai"}

        return None

    async def get_ocr_config(self) -> dict | None:
        """获取 OCR 配置（按优先级：百度 > 腾讯 > 阿里）。"""
        for provider in ["baidu_ocr", "tencent_ocr", "aliyun_ocr"]:
            config = await self.get_config(provider)
            if config and config.get("api_key"):
                return {**config, "provider": provider}
        return None


@lru_cache(maxsize=1)
def get_config_manager() -> ConfigManager:
    """获取配置管理器单例。"""
    return ConfigManager()
