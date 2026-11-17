from __future__ import annotations

import argparse
import logging
import time
from datetime import datetime

from app.core.config import settings
from app.core.database import init_db, SessionLocal
from app.core.jobs import run_job_inline
from app.core.logging import configure_logging

configure_logging()

logger = logging.getLogger("nexus.worker")


def poll_once(db) -> int:
    from app.models import Job, JobStatus
    job = (
        db.query(Job)
        .filter(Job.status == JobStatus.QUEUED)
        .order_by(Job.created_at.asc())
        .first()
    )
    if job is None:
        return 0
    job.status = JobStatus.RUNNING
    job.started_at = datetime.utcnow()
    db.commit()

    # in-process execution (thread-safe for the data engine)
    run_job_inline(job.id, lambda payload: _dispatch_task(job.task, payload))
    return 1


def _dispatch_task(task: str, payload: dict):
    """Dispatch a background job task to the appropriate handler."""
    try:
        if task == "ml_train":
            return _handle_ml_train(payload)
        if task == "report_generate":
            return _handle_report_generate(payload)
        if task == "data_export":
            return _handle_data_export(payload)
        if task == "demo_check":
            return {"ok": True}
        if task == "ping":
            return {"pong": True}
        logger.warning("Unknown task type: %s", task)
        return {"task": task, "payload": payload, "error": "Unknown task type"}
    except Exception as e:
        logger.exception("Task %s failed: %s", task, e)
        raise


def _handle_ml_train(payload: dict) -> dict:
    from app.repositories.dataset_repo import load_dataset_df
    from app.services import ml as ml_service
    from app.models import MLModel, MLRun
    from app.core.database import SessionLocal

    dataset_id = payload.get("dataset_id")
    target = payload.get("target")
    features = payload.get("features")
    task = payload.get("task")
    algorithms = payload.get("algorithms")
    test_size = payload.get("test_size", 0.25)

    if not dataset_id or not target:
        raise ValueError("dataset_id and target are required")

    db = SessionLocal()
    try:
        from app.repositories.dataset_repo import get_dataset_for_user
        from app.models import Dataset
        ds = db.query(Dataset).filter(Dataset.id == dataset_id).first()
        if not ds:
            raise ValueError(f"Dataset {dataset_id} not found")
        df = load_dataset_df(ds)
    finally:
        db.close()

    result = ml_service.run_ml(df, target=target, features=features, task=task,
                               algorithms=algorithms, test_size=test_size)

    db = SessionLocal()
    try:
        model = MLModel(dataset_id=ds.id, name=f"Model on {target}", task=result["task"],
                        target=target, metrics=result.get("best_metrics", {}),
                        feature_importance=result.get("feature_importance", []),
                        path="auto")
        db.add(model)
        db.commit()
        db.refresh(model)
        for r in result.get("models", []):
            db.add(MLRun(model_id=model.id, algorithm=r.get("algorithm", ""), metrics=r.get("metrics", {}),
                         config={"target": target}, duration_ms=r.get("duration_ms", 0)))
        db.commit()
        return {"model_id": model.id, "result": result}
    finally:
        db.close()


def _handle_report_generate(payload: dict) -> dict:
    # Placeholder for report generation
    return {"status": "not_implemented"}


def _handle_data_export(payload: dict) -> dict:
    # Placeholder for data export
    return {"status": "not_implemented"}


def main() -> None:
    parser = argparse.ArgumentParser(description="Nexus Data worker")
    parser.add_argument("--poll", type=float, default=2.0, help="seconds between polls")
    args = parser.parse_args()

    settings.ensure_dirs()
    init_db()
    logger.info("Worker started (poll %.1fs)", args.poll)
    while True:
        db = SessionLocal()
        try:
            processed = poll_once(db)
            if not processed:
                time.sleep(args.poll)
        except Exception as exc:
            logger.warning("worker poll error: %s", exc)
            time.sleep(args.poll)
        finally:
            db.close()


if __name__ == "__main__":
    main()