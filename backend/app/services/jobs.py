from __future__ import annotations

import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Callable

from ..models import Job, utc_now


JOBS: dict[str, Job] = {}
LOCK = threading.Lock()
EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="dreamhome-job")
MAX_RETAINED_TERMINAL_JOBS = 200
TERMINAL_STATUSES = {"completed", "failed"}
ACTIVE_STATUSES = {"queued", "running"}


def _prune_terminal_jobs_locked() -> None:
    terminal = sorted(
        (job for job in JOBS.values() if job.status in TERMINAL_STATUSES),
        key=lambda item: item.updated_at,
    )
    overflow = len(terminal) - MAX_RETAINED_TERMINAL_JOBS
    for job in terminal[:max(0, overflow)]:
        JOBS.pop(job.id, None)


def create_job(project_id: str, kind: str) -> Job:
    job = Job(id=str(uuid.uuid4()), project_id=project_id, kind=kind)
    with LOCK:
        _prune_terminal_jobs_locked()
        JOBS[job.id] = job
    return job


def find_active_job(project_id: str, kind: str) -> Job | None:
    with LOCK:
        matching = [
            job for job in JOBS.values()
            if job.project_id == project_id and job.kind == kind and job.status in ACTIVE_STATUSES
        ]
        if not matching:
            return None
        return max(matching, key=lambda item: item.updated_at)


def get_job(job_id: str) -> Job:
    with LOCK:
        if job_id not in JOBS:
            raise KeyError(job_id)
        return JOBS[job_id]


def update_job(job_id: str, progress: int, message: str, **changes) -> None:
    with LOCK:
        job = JOBS.get(job_id)
        if job is None:
            raise KeyError(job_id)
        job.progress = max(0, min(100, progress))
        job.message = message
        job.updated_at = utc_now()
        for key, value in changes.items():
            setattr(job, key, value)
        if job.status in TERMINAL_STATUSES:
            _prune_terminal_jobs_locked()


def submit(
    job: Job,
    task: Callable[[Callable[[int, str], None]], tuple[Path, str] | tuple[Path, str, dict[str, Any]]],
) -> Job:
    def runner() -> None:
        update_job(job.id, 1, "Starting", status="running")
        try:
            result = task(lambda progress, message: update_job(job.id, progress, message))
            if len(result) == 3:
                output_path, output_url, metadata = result
            else:
                output_path, output_url = result
                metadata = {}
            update_job(
                job.id,
                100,
                "Complete",
                status="completed",
                output_path=str(output_path),
                output_url=output_url,
                metadata=metadata,
                error=None,
            )
        except Exception as exc:
            update_job(job.id, 100, "Failed", status="failed", error=str(exc), message=str(exc))

    try:
        EXECUTOR.submit(runner)
    except Exception as exc:
        update_job(job.id, 100, "Failed to queue", status="failed", error=str(exc), message=str(exc))
        raise
    return job
