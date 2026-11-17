from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.errors import NotFoundError
from app.models import Chart
from app.repositories.dataset_repo import get_dataset_for_user, load_dataset_df
from app.schemas import ChartRequest
from app.services import charts as chart_service

router = APIRouter(prefix="/api/charts", tags=["charts"])


@router.post("/build")
def build_chart(payload: ChartRequest, dataset_id: str | None = None,
                user=Depends(get_current_user), db: Session = Depends(get_db)):
    ds = get_dataset_for_user(db, dataset_id, user.id) if dataset_id else None
    if ds is None:
        # dataset id from config
        cds = payload.config.get("dataset_id")
        if cds:
            ds = get_dataset_for_user(db, cds, user.id)
    if ds is None:
        raise NotFoundError("A dataset is required to build a chart.")
    df = load_dataset_df(ds)
    data, error = chart_service.build_chart_data(df, payload.chart_type, payload.config)
    if error:
        return {"data": None, "error": error, "chart_type": payload.chart_type}
    return {"data": data, "chart_type": payload.chart_type, "dataset_id": ds.id}


@router.get("/recommend")
def recommend(dataset_id: str, user=Depends(get_current_user), db: Session = Depends(get_db)):
    ds = get_dataset_for_user(db, dataset_id, user.id)
    df = load_dataset_df(ds)
    return {"recommendations": chart_service.recommend_charts(df)}


@router.get("/schema")
def chart_schema(dataset_id: str, user=Depends(get_current_user), db: Session = Depends(get_db)):
    ds = get_dataset_for_user(db, dataset_id, user.id)
    df = load_dataset_df(ds)
    return {"columns": chart_service.schema_profile(df)}


@router.post("/save")
def save_chart(payload: ChartRequest, dataset_id: str,
               user=Depends(get_current_user), db: Session = Depends(get_db)):
    ds = get_dataset_for_user(db, dataset_id, user.id)
    df = load_dataset_df(ds)
    data, error = chart_service.build_chart_data(df, payload.chart_type, payload.config)
    c = Chart(project_id=payload.config.get("project_id") or ds.project_id, dataset_id=ds.id,
              name=payload.name, chart_type=payload.chart_type, config=payload.config,
              data={"data": data} if not error else None)
    db.add(c)
    db.commit()
    db.refresh(c)
    return {"chart": _c(c)}


@router.get("/saved")
def saved_charts(user=Depends(get_current_user), db: Session = Depends(get_db)):
    charts = db.query(Chart).order_by(Chart.updated_at.desc()).limit(200).all()
    return {"charts": [_c(c) for c in charts]}


@router.delete("/{chart_id}")
def delete_chart(chart_id: str, user=Depends(get_current_user), db: Session = Depends(get_db)):
    c = db.query(Chart).filter(Chart.id == chart_id).first()
    if not c:
        raise NotFoundError("Chart not found.")
    db.delete(c)
    db.commit()
    return {"ok": True}


def _c(c: Chart) -> dict:
    return {
        "id": c.id, "name": c.name, "chart_type": c.chart_type, "config": c.config,
        "dataset_id": c.dataset_id, "project_id": c.project_id,
        "data": c.data,
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }