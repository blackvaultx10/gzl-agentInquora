from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

if TYPE_CHECKING:
    pass


class ProviderConfig(Base):
    """????????????"""

    __tablename__ = "provider_configs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    provider_type: Mapped[str] = mapped_column(String(50), index=True, comment="?????: baidu_ocr, tencent_ocr, deepseek, openai")
    name: Mapped[str] = mapped_column(String(100), comment="????")
    api_key: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="API Key (????)")
    secret_key: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="Secret Key (????)")
    base_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True, comment="??URL")
    model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, comment="????")
    extra_config: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="????JSON")
    is_active: Mapped[bool] = mapped_column(default=True, comment="????")
    is_encrypted: Mapped[bool] = mapped_column(default=False, comment="?????")
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


class InquiryProject(Base):
    """??????"""

    __tablename__ = "inquiry_projects"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(200), unique=True, index=True, comment="????")
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="????")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    last_processed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
        comment="????????????",
    )

    def __repr__(self) -> str:
        return f"<InquiryProject {self.id}: {self.name}>"
