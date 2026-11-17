from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.core.errors import NotFoundError
from app.models import (
    Chart, Dashboard, Dataset, Notebook, Project, Query, Report,
)
from app.repositories.dataset_repo import dataset_dict
from app.schemas import ExportRequest
from app.services import export as export_service

from app.repositories.dataset_repo import get_dataset_for_user, load_dataset_df

router = APIRouter(tags=["search-jobs-export"])


# ── Global Search ─────────────────────────────────────────────────────────
@router.get("/api/search")
def global_search(q: str = "", user=Depends(get_current_user), db: Session = Depends(get_db)):
    query = (q or "").strip().lower()
    results = {"projects": [], "datasets": [], "charts": [], "dashboards": [], "reports": [],
               "queries": [], "notebooks": [], "columns": []}
    if query:
        def _lk(term):
            return f"%{term}%"
        for p in db.query(Project).filter(Project.name.ilike(_lk(query))).limit(10):
            results["projects"].append({"id": p.id, "name": p.name, "description": p.description, "type": "project"})
        for d in db.query(Dataset).filter(Dataset.name.ilike(_lk(query))).limit(10):
            results["datasets"].append(dataset_dict(d) | {"type": "dataset"})
        for c in db.query(Chart).filter(Chart.name.ilike(_lk(query))).limit(10):
            results["charts"].append({"id": c.id, "name": c.name, "type": "chart", "chart_type": c.chart_type, "dataset_id": c.dataset_id})
        for d in db.query(Dashboard).filter(Dashboard.name.ilike(_lk(query))).limit(10):
            results["dashboards"].append({"id": d.id, "name": d.name, "type": "dashboard"})
        for r in db.query(Report).filter(Report.name.ilike(_lk(query))).limit(10):
            results["reports"].append({"id": r.id, "name": r.name, "type": "report"})
        for n in db.query(Notebook).filter(Notebook.name.ilike(_lk(query))).limit(10):
            results["notebooks"].append({"id": n.id, "name": n.name, "type": "notebook"})
        for q2 in db.query(Query).filter(Query.sql.ilike(_lk(query)), Query.is_saved == True).limit(10):
            results["queries"].append({"id": q2.id, "name": q2.name, "sql": q2.sql[:80], "type": "query"})
        from app.models import DatasetColumn
        for dc in db.query(DatasetColumn).filter(DatasetColumn.name.ilike(_lk(query))).limit(20):
            ds = db.query(Dataset).filter(Dataset.id == dc.dataset_id).first()
            results["columns"].append({"dataset_id": dc.dataset_id, "dataset_name": ds.name if ds else "",
                                       "name": dc.name, "type": "column"})
    return results


# ── Export ────────────────────────────────────────────────────────────────
@router.post("/api/export")
def export_data(payload: ExportRequest, user=Depends(get_current_user), db: Session = Depends(get_db)):
    if payload.dataset_id:
        ds = get_dataset_for_user(db, payload.dataset_id, user.id)
        df = load_dataset_df(ds)
        if payload.limit and len(df) > payload.limit:
            df = df.head(payload.limit)
        path, fname = export_service.export_dataframe(df, payload.format)
    elif payload.sql and payload.project_id:
        from app.services import sql_engine
        from app.models import Dataset
        tables = {}
        for d in db.query(Dataset).filter(Dataset.project_id == payload.project_id).all():
            tables[d.name] = load_dataset_df(d)
            tables[d.id] = tables[d.name]
        result = sql_engine.execute_sql(payload.sql, tables, limit=payload.limit)
        path, fname = export_service.export_sql_result(result.columns, result.rows, payload.format)
    else:
        raise NotFoundError("Provide dataset_id or sql + project_id to export.")
    return {"file": fname, "url": f"/api/export/download/{fname}", "format": payload.format}


@router.get("/api/export/download/{fname}")
def download_export(fname: str, user=Depends(get_current_user)):
    path = Path(settings.export_dir) / Path(fname).name
    if not path.exists():
        raise NotFoundError("Export file not found or expired.")
    return FileResponse(path, filename=fname)


# ── Jobs ──────────────────────────────────────────────────────────────────
@router.get("/api/jobs")
def list_jobs(user=Depends(get_current_user), db: Session = Depends(get_db)):
    from app.models import Job
    jobs = db.query(Job).order_by(Job.created_at.desc()).limit(100).all()
    return {"jobs": [_j(j) for j in jobs]}


@router.get("/api/jobs/{job_id}")
def get_job(job_id: str, user=Depends(get_current_user), db: Session = Depends(get_db)):
    from app.models import Job
    j = db.query(Job).filter(Job.id == job_id).first()
    if not j:
        raise NotFoundError("Job not found.")
    return {"job": _j(j)}


def _j(j) -> dict:
    return {
        "id": j.id, "name": j.name, "task": j.task, "status": j.status,
        "progress": j.progress, "result": j.result, "error": j.error,
        "created_at": j.created_at.isoformat() if j.created_at else None,
        "completed_at": j.completed_at.isoformat() if j.completed_at else None,
    }


# ── Meta / Health ─────────────────────────────────────────────────────────
@router.get("/health")
def health():
    return {"status": "ok", "app": "nexus-data", "time": __import__("datetime").datetime.utcnow().isoformat() + "Z"}


@router.get("/ready")
def ready(db: Session = Depends(get_db)):
    try:
        db.execute(__import__("sqlalchemy").text("SELECT 1"))
        return {"status": "ready", "database": "connected"}
    except Exception as exc:  # noqa: BLE001
        return {"status": "not_ready", "database": str(exc)}