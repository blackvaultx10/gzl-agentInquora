from __future__ import annotations

import asyncio
import threading
from datetime import datetime, timezone
from functools import lru_cache
from uuid import uuid4

from sqlalchemy import select

from app.db import async_session_maker
from app.models import InquiryJobProgress, InquiryJobSnapshot
from app.models_db import InquiryProject
from app.services.pipeline import InquiryPipeline, InputFile


class InquiryJobManager:
    def __init__(self) -> None:
        self._jobs: dict[str, InquiryJobSnapshot] = {}
        self._lock = threading.Lock()

    async def create_job(
        self,
        *,
        project: InquiryProject,
        files: list[InputFile],
        pipeline: InquiryPipeline,
    ) -> InquiryJobSnapshot:
        now = datetime.now(timezone.utc)
        snapshot = InquiryJobSnapshot(
            job_id=f"job-{uuid4().hex[:12]}",
            status="queued",
            project_id=project.id,
            project_name=project.name,
            created_at=now,
            updated_at=now,
            progress=InquiryJobProgress(
                step="等待处理",
                current=0,
                total=len(files),
                percent=0,
                current_file_name=None,
            ),
        )

        with self._lock:
            self._jobs[snapshot.job_id] = snapshot

        threading.Thread(
            target=self._run_job_sync,
            args=(snapshot.job_id, project.id, project.name, files, pipeline),
            daemon=True,
        ).start()
        return snapshot

    async def get_job(self, job_id: str) -> InquiryJobSnapshot | None:
        with self._lock:
            snapshot = self._jobs.get(job_id)
            if snapshot is None:
                return None
            return snapshot.model_copy(deep=True)

    async def _store_job(self, snapshot: InquiryJobSnapshot) -> None:
        with self._lock:
            self._jobs[snapshot.job_id] = snapshot

    async def _update_job(self, job_id: str, **changes) -> InquiryJobSnapshot | None:
        with self._lock:
            snapshot = self._jobs.get(job_id)
            if snapshot is None:
                return None
            updated = snapshot.model_copy(
                update={
                    **changes,
                    "updated_at": datetime.now(timezone.utc),
                }
            )
            self._jobs[job_id] = updated
            return updated

    def _run_job_sync(
        self,
        job_id: str,
        project_id: int,
        project_name: str,
        files: list[InputFile],
        pipeline: InquiryPipeline,
    ) -> None:
        asyncio.run(self._run_job(job_id, project_id, project_name, files, pipeline))

    def _progress_percent(self, step: str, current: int, total: int) -> int:
        total = max(total, 1)
        if step == "正在解析文件":
            return min(80, max(5, int((current / total) * 80)))
        if step == "正在抽取询价项":
            return 88
        if step == "正在归并项目清单":
            return 94
        if step == "正在整理参考价":
            return 98
        if step == "处理完成":
            return 100
        return min(99, max(0, int((current / total) * 100)))

    async def _mark_project_processed(self, project_id: int) -> None:
        async with async_session_maker() as session:
            result = await session.execute(
                select(InquiryProject).where(InquiryProject.id == project_id)
            )
            project = result.scalar_one_or_none()
            if project is None:
                return
            project.last_processed_at = datetime.now(timezone.utc)
            await session.commit()

    async def _run_job(
        self,
        job_id: str,
        project_id: int,
        project_name: str,
        files: list[InputFile],
        pipeline: InquiryPipeline,
    ) -> None:
        total_files = len(files)

        async def on_progress(step: str, current: int, total: int, filename: str | None) -> None:
            await self._update_job(
                job_id,
                status="processing",
                progress=InquiryJobProgress(
                    step=step,
                    current=current,
                    total=total,
                    percent=self._progress_percent(step, current, total),
                    current_file_name=filename,
                ),
            )

        await self._update_job(
            job_id,
            status="processing",
            progress=InquiryJobProgress(
                step="正在准备文件",
                current=0,
                total=total_files,
                percent=1 if total_files else 0,
                current_file_name=None,
            ),
        )

        try:
            result = await pipeline.run_inputs(
                files,
                project_name=project_name,
                progress_callback=on_progress,
            )
            await self._mark_project_processed(project_id)
            await self._update_job(
                job_id,
                status="completed",
                result=result,
                error=None,
                progress=InquiryJobProgress(
                    step="处理完成",
                    current=total_files,
                    total=total_files,
                    percent=100,
                    current_file_name=None,
                ),
            )
        except Exception as exc:
            await self._update_job(
                job_id,
                status="failed",
                error=str(exc),
                progress=InquiryJobProgress(
                    step="处理失败",
                    current=0,
                    total=total_files,
                    percent=100,
                    current_file_name=None,
                ),
            )


@lru_cache(maxsize=1)
def get_job_manager() -> InquiryJobManager:
    return InquiryJobManager()
