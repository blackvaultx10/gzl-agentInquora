from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import ProjectCreatePayload, ProjectSummary
from app.models_db import InquiryProject

router = APIRouter(prefix="/projects", tags=["projects"])


def _to_summary(project: InquiryProject) -> ProjectSummary:
    return ProjectSummary(
        id=project.id,
        name=project.name,
        description=project.description,
        created_at=project.created_at,
        updated_at=project.updated_at,
        last_processed_at=project.last_processed_at,
    )


@router.get("", response_model=list[ProjectSummary])
async def list_projects(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[ProjectSummary]:
    result = await db.execute(
        select(InquiryProject).order_by(
            InquiryProject.last_processed_at.is_(None),
            InquiryProject.last_processed_at.desc(),
            InquiryProject.updated_at.desc(),
            InquiryProject.id.desc(),
        )
    )
    return [_to_summary(project) for project in result.scalars().all()]


@router.post("", response_model=ProjectSummary, status_code=status.HTTP_201_CREATED)
async def create_project(
    payload: ProjectCreatePayload,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProjectSummary:
    normalized_name = payload.name.strip()
    if not normalized_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="项目名称不能为空。",
        )

    existing = await db.execute(
        select(InquiryProject).where(InquiryProject.name == normalized_name)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"项目 {normalized_name} 已存在。",
        )

    project = InquiryProject(
        name=normalized_name,
        description=(payload.description or "").strip() or None,
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return _to_summary(project)
