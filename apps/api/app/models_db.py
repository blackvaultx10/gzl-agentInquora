from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

if TYPE_CHECKING:
    pass


class ProviderConfig(Base):
    """第三方服务提供商配置表。"""

    __tablename__ = "provider_configs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    provider_type: Mapped[str] = mapped_column(String(50), index=True, comment="提供商类型: baidu_ocr, tencent_ocr, deepseek, openai")
    name: Mapped[str] = mapped_column(String(100), comment="显示名称")
    api_key: Mapped[str | None] = mapped_column(Text, nullable=True, comment="API Key (加密存储)")
    secret_key: Mapped[str | None] = mapped_column(Text, nullable=True, comment="Secret Key (加密存储)")
    base_url: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="基础URL")
    model: Mapped[str | None] = mapped_column(String(100), nullable=True, comment="模型名称")
    extra_config: Mapped[str | None] = mapped_column(Text, nullable=True, comment="额外配置JSON")
    is_active: Mapped[bool] = mapped_column(default=True, comment="是否启用")
    is_encrypted: Mapped[bool] = mapped_column(default=False, comment="是否已加密")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return f"<ProviderConfig {self.provider_type}: {self.name}>"
