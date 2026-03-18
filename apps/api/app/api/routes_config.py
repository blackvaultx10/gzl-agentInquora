from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models_db import ProviderConfig
from app.security import decrypt_value, encrypt_value, mask_value

router = APIRouter(prefix="/configs", tags=["configs"])


class ProviderConfigCreate(BaseModel):
    """创建配置请求模型。"""

    provider_type: str = Field(..., description="提供商类型: baidu_ocr, tencent_ocr, deepseek, openai")
    name: str = Field(..., description="显示名称")
    api_key: str | None = Field(None, description="API Key")
    secret_key: str | None = Field(None, description="Secret Key")
    base_url: str | None = Field(None, description="基础URL")
    model: str | None = Field(None, description="模型名称")
    extra_config: str | None = Field(None, description="额外配置JSON")
    is_active: bool = Field(True, description="是否启用")


class ProviderConfigResponse(BaseModel):
    """配置响应模型（脱敏）。"""

    id: int
    provider_type: str
    name: str
    api_key_masked: str | None = Field(None, alias="api_key")
    has_secret_key: bool = False
    base_url: str | None = None
    model: str | None = None
    is_active: bool
    created_at: str
    updated_at: str

    class Config:
        populate_by_name = True


class ProviderConfigDetail(BaseModel):
    """配置详情响应（包含明文密钥，仅用于编辑）。"""

    id: int
    provider_type: str
    name: str
    api_key: str | None = None
    secret_key: str | None = None
    base_url: str | None = None
    model: str | None = None
    extra_config: str | None = None
    is_active: bool
    created_at: str
    updated_at: str


@router.get("", response_model=list[ProviderConfigResponse])
async def list_configs(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[ProviderConfigResponse]:
    """获取所有配置列表（脱敏）。"""
    result = await db.execute(select(ProviderConfig).order_by(ProviderConfig.provider_type))
    configs = result.scalars().all()

    response = []
    for config in configs:
        response.append(
            ProviderConfigResponse(
                id=config.id,
                provider_type=config.provider_type,
                name=config.name,
                api_key=mask_value(decrypt_value(config.api_key)),
                has_secret_key=config.secret_key is not None,
                base_url=config.base_url,
                model=config.model,
                is_active=config.is_active,
                created_at=config.created_at.isoformat() if config.created_at else "",
                updated_at=config.updated_at.isoformat() if config.updated_at else "",
            )
        )
    return response


@router.get("/providers", response_model=list[dict])
async def get_provider_types() -> list[dict]:
    """获取支持的提供商类型列表。"""
    return [
        {"type": "deepseek", "name": "DeepSeek", "description": "DeepSeek AI 对话", "fields": ["api_key", "base_url", "model"]},
        {"type": "openai", "name": "OpenAI", "description": "OpenAI GPT", "fields": ["api_key", "base_url", "model"]},
        {"type": "baidu_ocr", "name": "百度智能云 OCR", "description": "百度文字识别", "fields": ["api_key", "secret_key"]},
        {"type": "tencent_ocr", "name": "腾讯云 OCR", "description": "腾讯云文字识别", "fields": ["api_key", "secret_key"]},
        {"type": "aliyun_ocr", "name": "阿里云 OCR", "description": "阿里云文字识别", "fields": ["api_key", "secret_key"]},
    ]


@router.post("", response_model=ProviderConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_config(
    config_data: ProviderConfigCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProviderConfigResponse:
    """创建新配置。"""
    # 检查是否已存在同类型配置
    result = await db.execute(
        select(ProviderConfig).where(ProviderConfig.provider_type == config_data.provider_type)
    )
    existing = result.scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"类型为 {config_data.provider_type} 的配置已存在，请更新或删除后重新创建",
        )

    # 加密敏感字段
    new_config = ProviderConfig(
        provider_type=config_data.provider_type,
        name=config_data.name,
        api_key=encrypt_value(config_data.api_key),
        secret_key=encrypt_value(config_data.secret_key),
        base_url=config_data.base_url,
        model=config_data.model,
        extra_config=config_data.extra_config,
        is_active=config_data.is_active,
        is_encrypted=True,
    )

    db.add(new_config)
    await db.commit()
    await db.refresh(new_config)

    return ProviderConfigResponse(
        id=new_config.id,
        provider_type=new_config.provider_type,
        name=new_config.name,
        api_key=mask_value(config_data.api_key),
        has_secret_key=new_config.secret_key is not None,
        base_url=new_config.base_url,
        model=new_config.model,
        is_active=new_config.is_active,
        created_at=new_config.created_at.isoformat() if new_config.created_at else "",
        updated_at=new_config.updated_at.isoformat() if new_config.updated_at else "",
    )


@router.get("/{provider_type}", response_model=ProviderConfigDetail)
async def get_config(
    provider_type: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProviderConfigDetail:
    """获取单个配置详情（包含明文密钥）。"""
    result = await db.execute(
        select(ProviderConfig).where(ProviderConfig.provider_type == provider_type)
    )
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"未找到类型为 {provider_type} 的配置",
        )

    return ProviderConfigDetail(
        id=config.id,
        provider_type=config.provider_type,
        name=config.name,
        api_key=decrypt_value(config.api_key),
        secret_key=decrypt_value(config.secret_key),
        base_url=config.base_url,
        model=config.model,
        extra_config=config.extra_config,
        is_active=config.is_active,
        created_at=config.created_at.isoformat() if config.created_at else "",
        updated_at=config.updated_at.isoformat() if config.updated_at else "",
    )


@router.put("/{provider_type}", response_model=ProviderConfigResponse)
async def update_config(
    provider_type: str,
    config_data: ProviderConfigCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProviderConfigResponse:
    """更新配置。"""
    result = await db.execute(
        select(ProviderConfig).where(ProviderConfig.provider_type == provider_type)
    )
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"未找到类型为 {provider_type} 的配置",
        )

    # 更新字段
    config.name = config_data.name
    if config_data.api_key is not None:
        config.api_key = encrypt_value(config_data.api_key)
    if config_data.secret_key is not None:
        config.secret_key = encrypt_value(config_data.secret_key)
    config.base_url = config_data.base_url
    config.model = config_data.model
    config.extra_config = config_data.extra_config
    config.is_active = config_data.is_active
    config.is_encrypted = True

    await db.commit()
    await db.refresh(config)

    return ProviderConfigResponse(
        id=config.id,
        provider_type=config.provider_type,
        name=config.name,
        api_key=mask_value(decrypt_value(config.api_key)),
        has_secret_key=config.secret_key is not None,
        base_url=config.base_url,
        model=config.model,
        is_active=config.is_active,
        created_at=config.created_at.isoformat() if config.created_at else "",
        updated_at=config.updated_at.isoformat() if config.updated_at else "",
    )


@router.delete("/{provider_type}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_config(
    provider_type: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """删除配置。"""
    result = await db.execute(
        select(ProviderConfig).where(ProviderConfig.provider_type == provider_type)
    )
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"未找到类型为 {provider_type} 的配置",
        )

    await db.delete(config)
    await db.commit()
