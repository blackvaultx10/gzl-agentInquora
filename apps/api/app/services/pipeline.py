from __future__ import annotations

import asyncio
import inspect
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status

from app.config import Settings
from app.models import InquiryResult
from app.services.boq import ProjectBoqBuilder
from app.services.extractor import ParameterExtractor
from app.services.parsers import parse_content
from app.services.pricing import PricingEngine


ProgressCallback = Callable[[str, int, int, str | None], Awaitable[None] | None]


@dataclass
class InputFile:
    filename: str
    content: bytes


class InquiryPipeline:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.extractor = ParameterExtractor(settings)
        self.boq_builder = ProjectBoqBuilder()
        self.pricing = PricingEngine(settings)

    async def prepare_inputs(self, files: list[UploadFile]) -> list[InputFile]:
        prepared: list[InputFile] = []
        for upload in files:
            if not upload.filename:
                continue
            prepared.append(InputFile(filename=upload.filename, content=await upload.read()))
        return prepared

    async def _emit_progress(
        self,
        callback: ProgressCallback | None,
        *,
        step: str,
        current: int,
        total: int,
        filename: str | None = None,
    ) -> None:
        if callback is None:
            return
        result = callback(step, current, total, filename)
        if inspect.isawaitable(result):
            await result

    async def _process_single_file(self, upload: InputFile, max_pages: int = 0) -> tuple | None:
        if not upload.filename:
            return None
        try:
            parsed_document, raw_text = await parse_content(
                upload.filename,
                upload.content,
                max_pages=max_pages,
            )
            return parsed_document, raw_text
        except Exception as exc:
            return None, f"处理失败: {exc}"

    async def run(
        self,
        files: list[UploadFile],
        max_pages: int = 0,
        project_name: str | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> InquiryResult:
        prepared_files = await self.prepare_inputs(files)
        return await self.run_inputs(
            prepared_files,
            max_pages=max_pages,
            project_name=project_name,
            progress_callback=progress_callback,
        )

    async def run_inputs(
        self,
        files: list[InputFile],
        max_pages: int = 0,
        project_name: str | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> InquiryResult:
        if not files:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="至少上传一个文件。",
            )

        documents = []
        raw_texts = []
        warnings: list[str] = []
        total_files = len(files)

        for index, file in enumerate(files, start=1):
            await self._emit_progress(
                progress_callback,
                step="正在解析文件",
                current=index,
                total=total_files,
                filename=file.filename,
            )
            result = await self._process_single_file(file, max_pages=max_pages)
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

        await self._emit_progress(
            progress_callback,
            step="正在抽取询价项",
            current=total_files,
            total=total_files,
        )
        extracted, mode = await asyncio.to_thread(self.extractor.extract, documents, raw_texts)
        warnings.extend(extracted.warnings)

        await self._emit_progress(
            progress_callback,
            step="正在归并项目清单",
            current=total_files,
            total=total_files,
        )
        project_items, boq_warnings = await asyncio.to_thread(
            self.boq_builder.build,
            extracted.items,
            documents,
            raw_texts,
        )
        warnings.extend(boq_warnings)

        await self._emit_progress(
            progress_callback,
            step="正在整理参考价",
            current=total_files,
            total=total_files,
        )
        priced_items, summary = await asyncio.to_thread(self.pricing.price_items, project_items)
        resolved_project_name = self.boq_builder.infer_project_name(documents, project_name)

        await self._emit_progress(
            progress_callback,
            step="处理完成",
            current=total_files,
            total=total_files,
        )
        return InquiryResult(
            request_id=f"inq-{uuid4().hex[:10]}",
            project_name=resolved_project_name,
            created_at=datetime.now(timezone.utc),
            extraction_mode=mode,
            pricing_mode="reference_only",
            documents=documents,
            items=priced_items,
            warnings=sorted(set(warnings)),
            summary=summary,
        )
