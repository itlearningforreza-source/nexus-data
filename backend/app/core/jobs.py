from __future__ import annotations

import threading
import traceback
import uuid
from datetime import datetime
from typing import Any, Callable

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models import Job, JobStatus
from app.core.logging import configure_logging

configure_logging()
import logging

logger = logging.getLogger("nexus.jobs")

RUNNING: dict[str, threading.Thread] = {}


def create_job(db: Session, *, name: str, task: str, user_id: int | None,
               organization_id: int | None, payload: dict[str, Any] | None = None) -> Job:
    job = Job(
        id=str(uuid.uuid4()),
        name=name,
        task=task,
        payload=payload or {},
        status=JobStatus.QUEUED,
        user_id=user_id,
        organization_id=organization_id,
        created_at=datetime.utcnow(),
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def update_job(db: Session, job_id: str, **fields) -> Job:
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        return None
    for k, v in fields.items():
        setattr(job, k, v)
    job.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(job)
    return job


def run_job_async(job_id: str, fn: Callable[[dict[str, Any]], Any]) -> None:
    def _runner() -> None:
        db = SessionLocal()
        try:
            job = update_job(db, job_id, status=JobStatus.RUNNING, started_at=datetime.utcnow())
            payload = job.payload or {} if job else {}
            try:
                result = fn(payload)
                update_job(
                    db, job_id, status=JobStatus.COMPLETED,
                    result=result if not isinstance(result, Exception) else None,
                    completed_at=datetime.utcnow(),
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("job %s failed: %s", job_id, exc)
                update_job(
                    db, job_id, status=JobStatus.FAILED,
                    error={"message": str(exc), "traceback": traceback.format_exc()},
                    completed_at=datetime.utcnow(),
                )
        finally:
            db.close()
            RUNNING.pop(job_id, None)

    thread = threading.Thread(target=_runner, daemon=True, name=f"job-{job_id}")
    RUNNING[job_id] = thread
    thread.start()


def run_job_inline(job_id: str, fn: Callable[[dict[str, Any]], Any]) -> None:
    db = SessionLocal()
    try:
        job = update_job(db, job_id, status=JobStatus.RUNNING, started_at=datetime.utcnow())
        payload = job.payload or {} if job else {}
        try:
            result = fn(payload)
            update_job(
                db, job_id, status=JobStatus.COMPLETED,
                result=result if not isinstance(result, Exception) else None,
                completed_at=datetime.utcnow(),
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("job %s failed: %s", job_id, exc)
            update_job(
                db, job_id, status=JobStatus.FAILED,
                error={"message": str(exc), "traceback": traceback.format_exc()},
                completed_at=datetime.utcnow(),
            )
    finally:
        db.close()


def dispatch_job(db: Session, *, name: str, task: str, fn: Callable[[dict[str, Any]], Any],
                 user_id: int | None, organization_id: int | None,
                 payload: dict[str, Any] | None = None) -> Job:
    from app.core.config import settings
    job = create_job(db, name=name, task=task, user_id=user_id,
                     organization_id=organization_id, payload=payload)
    if settings.WORKER_INLINE:
        run_job_inline(job.id, fn)
    else:
        run_job_async(job.id, fn)
    return job