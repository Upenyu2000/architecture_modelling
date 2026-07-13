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


def create_job(project_id: str, kind: str) -> Job:
    job = Job(id=str(uuid.uuid4()), project_id=project_id, kind=kind)
    with LOCK:
        JOBS[job.id] = job
    return job


def get_job(job_id: str) -> Job:
    with LOCK:
        if job_id not in JOBS:
            raise KeyError(job_id)
        return JOBS[job_id]


def update_job(job_id: str, progress: int, message: str, **changes) -> None:
    with LOCK:
        job = JOBS[job_id]
        job.progress = max(0, min(100, progress))
        job.message = message
        job.updated_at = utc_now()
        for key, value in changes.items():
            setattr(job, key, value)


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
            )
        except Exception as exc:
            update_job(job.id, 100, "Failed", status="failed", error=str(exc), message=str(exc))
    EXECUTOR.submit(runner)
    return job
