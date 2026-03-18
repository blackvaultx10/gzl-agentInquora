from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
TEMP_DIR = BASE_DIR / ".tmp"


LlmProvider = Literal["auto", "openai", "deepseek", "none"]


class Settings(BaseSettings):
    app_name: str = "Inquora Inquiry API"
    api_prefix: str = "/api/v1"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])
    price_catalog_path: Path = DATA_DIR / "price_catalog.csv"

    llm_provider: LlmProvider = "auto"
    openai_api_key: str | None = None
    openai_model: str = "gpt-5-mini"
    deepseek_api_key: str | None = None
    deepseek_model: str = "deepseek-chat"
    deepseek_base_url: str = "https://api.deepseek.com"
    llm_max_input_chars: int = 16000

    ocr_languages: list[str] = Field(default_factory=lambda: ["ch_sim", "en"])
    # OCR 配置 - 工程图纸专用优化
    # 策略：放大→分区→表格识别→去重
    pdf_ocr_render_scale: float = 3.0      # 工程图纸字小，需要更高渲染倍率
    pdf_ocr_max_side_px: int = 8000        # A0大图支持
    ocr_full_upscale_factor: float = 2.0   # 小字放大2倍识别
    ocr_tile_size_px: int = 1500           # 分块1500x1500（表格行高考虑）
    ocr_tile_overlap_px: int = 300         # 重叠300像素，避免表格行被切断
    ocr_tile_max_slices: int = 4           # 大图分4x4=16块，覆盖A0图纸
    ocr_tile_upscale_factor: float = 2.0   # 分块后也放大
    max_upload_size_mb: int = 50

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    return Settings()
