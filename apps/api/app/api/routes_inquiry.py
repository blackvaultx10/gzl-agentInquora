from __future__ import annotations

from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import StreamingResponse

from app.config import Settings, get_settings
from app.models import ExportFormat, ExportPayload, InquiryResult
from app.services.exporters import export_docx, export_xlsx
from app.services.pipeline import InquiryPipeline


router = APIRouter(prefix="/inquiry", tags=["inquiry"])


def get_pipeline(settings: Settings = Depends(get_settings)) -> InquiryPipeline:
    return InquiryPipeline(settings)


@router.post("/parse", response_model=InquiryResult)
async def parse_inquiry(
    files: list[UploadFile] = File(...),
    pipeline: InquiryPipeline = Depends(get_pipeline),
) -> InquiryResult:
    return await pipeline.run(files)


@router.post("/export")
async def export_inquiry(
    payload: ExportPayload,
    format: ExportFormat = Query(...),
) -> StreamingResponse:
    if format == "xlsx":
        stream = export_xlsx(payload.result)
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        filename = f"{payload.result.request_id}.xlsx"
    else:
        stream = export_docx(payload.result)
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        filename = f"{payload.result.request_id}.docx"

    return StreamingResponse(
        stream,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

