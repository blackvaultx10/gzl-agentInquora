from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


CurrencyCode = Literal["CNY", "USD"]
ExportFormat = Literal["xlsx", "docx"]
ExtractionMode = Literal["openai", "deepseek", "heuristic"]
PricingMode = Literal["reference_only", "supplier_quote"]
InquiryJobStatus = Literal["queued", "processing", "completed", "failed"]
DocumentRole = Literal["legend", "spec", "system", "plan", "other"]


class ParsedDocument(BaseModel):
    filename: str
    file_type: str
    parser: str
    document_role: DocumentRole = "other"
    text_excerpt: str
    warnings: list[str] = Field(default_factory=list)


class InquiryItem(BaseModel):
    boq_code: str | None = None
    name: str
    category: str | None = None
    specification: str | None = None
    material: str | None = None
    quantity: float = 1.0
    unit: str = "?"
    inquiry_method: str | None = None
    source_documents: list[str] = Field(default_factory=list)
    source_snippet: str
    confidence: float = 0.5
    vendor: str | None = None
    currency: CurrencyCode = "CNY"
    unit_price: float | None = None
    total_price: float | None = None
    price_basis: str | None = None
    match_score: float | None = None
    reference_vendor: str | None = None
    reference_unit_price: float | None = None
    reference_total_price: float | None = None
    reference_basis: str | None = None
    reference_match_score: float | None = None
    price_source: str | None = None
    anomalies: list[str] = Field(default_factory=list)


class InquirySummary(BaseModel):
    item_count: int
    reference_count: int
    pending_count: int
    flagged_count: int
    reference_subtotal: float
    currency: CurrencyCode = "CNY"


class InquiryResult(BaseModel):
    request_id: str
    project_name: str
    created_at: datetime
    extraction_mode: ExtractionMode
    pricing_mode: PricingMode = "reference_only"
    documents: list[ParsedDocument]
    items: list[InquiryItem]
    warnings: list[str] = Field(default_factory=list)
    summary: InquirySummary


class ExportPayload(BaseModel):
    result: InquiryResult


class ProjectCreatePayload(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)


class ProjectSummary(BaseModel):
    id: int
    name: str
    description: str | None = None
    created_at: datetime
    updated_at: datetime
    last_processed_at: datetime | None = None


class InquiryJobProgress(BaseModel):
    step: str = "????"
    current: int = 0
    total: int = 0
    percent: int = 0
    current_file_name: str | None = None


class InquiryJobSnapshot(BaseModel):
    job_id: str
    status: InquiryJobStatus
    project_id: int
    project_name: str
    created_at: datetime
    updated_at: datetime
    progress: InquiryJobProgress
    result: InquiryResult | None = None
    error: str | None = None
