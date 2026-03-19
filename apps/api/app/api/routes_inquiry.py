from __future__ import annotations

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.config import Settings, get_settings
from app.models import ExportFormat, ExportPayload, InquiryJobSnapshot, InquiryResult
from app.models_db import InquiryProject
from app.services.exporters import export_docx, export_xlsx
from app.services.jobs import InquiryJobManager, get_job_manager
from app.services.pipeline import InquiryPipeline


router = APIRouter(prefix="/inquiry", tags=["inquiry"])


def get_pipeline(settings: Settings = Depends(get_settings)) -> InquiryPipeline:
    return InquiryPipeline(settings)


def get_jobs() -> InquiryJobManager:
    return get_job_manager()


async def _get_project_or_404(db: AsyncSession, project_id: int) -> InquiryProject:
    result = await db.execute(
        select(InquiryProject).where(InquiryProject.id == project_id)
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"未找到项目 ID={project_id}",
        )
    return project


async def _touch_project(db: AsyncSession, project: InquiryProject) -> None:
    project.last_processed_at = datetime.now(timezone.utc)
    await db.commit()


@router.post("/parse", response_model=InquiryResult)
async def parse_inquiry(
    files: list[UploadFile] = File(...),
    project_id: int = Query(..., description="所属项目ID"),
    db: AsyncSession = Depends(get_db),
    pipeline: InquiryPipeline = Depends(get_pipeline),
) -> InquiryResult:
    project = await _get_project_or_404(db, project_id)
    result = await pipeline.run(files, project_name=project.name)
    await _touch_project(db, project)
    return result


@router.post(
    "/jobs",
    response_model=InquiryJobSnapshot,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_inquiry_job(
    files: list[UploadFile] = File(...),
    project_id: int = Query(..., description="所属项目ID"),
    db: AsyncSession = Depends(get_db),
    pipeline: InquiryPipeline = Depends(get_pipeline),
    jobs: InquiryJobManager = Depends(get_jobs),
) -> InquiryJobSnapshot:
    project = await _get_project_or_404(db, project_id)
    prepared_files = await pipeline.prepare_inputs(files)
    if not prepared_files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="至少上传一个有效文件。",
        )
    return await jobs.create_job(project=project, files=prepared_files, pipeline=pipeline)


@router.get("/jobs/{job_id}", response_model=InquiryJobSnapshot)
async def get_inquiry_job(
    job_id: str,
    jobs: InquiryJobManager = Depends(get_jobs),
) -> InquiryJobSnapshot:
    snapshot = await jobs.get_job(job_id)
    if snapshot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"未找到任务 {job_id}",
        )
    return snapshot


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
