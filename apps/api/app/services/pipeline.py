from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status

from app.config import Settings
from app.models import InquiryResult
from app.services.extractor import ParameterExtractor
from app.services.parsers import parse_upload
from app.services.pricing import PricingEngine


class InquiryPipeline:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.extractor = ParameterExtractor(settings)
        self.pricing = PricingEngine(settings)

    async def _process_single_file(self, upload: UploadFile) -> tuple | None:
        """处理单个文件。"""
        if not upload.filename:
            return None
        try:
            parsed_document, raw_text = await parse_upload(upload)
            return parsed_document, raw_text
        except Exception as exc:
            return None, f"处理失败: {exc}"

    async def run(self, files: list[UploadFile]) -> InquiryResult:
        if not files:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="至少上传一个文件。",
            )

        # 并行处理所有文件（最多3个并发，避免OCR限流）
        semaphore = asyncio.Semaphore(3)

        async def process_with_limit(upload: UploadFile):
            async with semaphore:
                return await self._process_single_file(upload)

        results = await asyncio.gather(*[process_with_limit(f) for f in files])

        documents = []
        raw_texts = []
        warnings: list[str] = []

        for result in results:
            if result is None:
                warnings.append("发现一个缺少文件名的上传项，已跳过。")
                continue
            parsed_document, raw_text = result
            if parsed_document:
                documents.append(parsed_document)
                raw_texts.append(raw_text)
                warnings.extend(parsed_document.warnings)

        if not documents:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="所有上传文件都无法解析。",
            )

        extracted, mode = self.extractor.extract(documents, raw_texts)
        warnings.extend(extracted.warnings)
        priced_items, summary = self.pricing.price_items(extracted.items)

        return InquiryResult(
            request_id=f"inq-{uuid4().hex[:10]}",
            created_at=datetime.now(timezone.utc),
            extraction_mode=mode,
            documents=documents,
            items=priced_items,
            warnings=sorted(set(warnings)),
            summary=summary,
        )
