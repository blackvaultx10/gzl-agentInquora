from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


CurrencyCode = Literal["CNY", "USD"]
ExportFormat = Literal["xlsx", "docx"]
ExtractionMode = Literal["openai", "deepseek", "heuristic"]


class ParsedDocument(BaseModel):
    filename: str
    file_type: str
    parser: str
    text_excerpt: str
    warnings: list[str] = Field(default_factory=list)


class InquiryItem(BaseModel):
    name: str
    category: str | None = None
    specification: str | None = None
    material: str | None = None
    quantity: float = 1.0
    unit: str = "项"
    source_snippet: str
    confidence: float = 0.5
    vendor: str | None = None
    currency: CurrencyCode = "CNY"
    unit_price: float | None = None
    total_price: float | None = None
    price_basis: str | None = None
    match_score: float | None = None
    anomalies: list[str] = Field(default_factory=list)


class InquirySummary(BaseModel):
    item_count: int
    matched_count: int
    flagged_count: int
    subtotal: float
    currency: CurrencyCode = "CNY"


class InquiryResult(BaseModel):
    request_id: str
    created_at: datetime
    extraction_mode: ExtractionMode
    documents: list[ParsedDocument]
    items: list[InquiryItem]
    warnings: list[str] = Field(default_factory=list)
    summary: InquirySummary


class ExportPayload(BaseModel):
    result: InquiryResult
