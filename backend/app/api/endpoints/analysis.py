from __future__ import annotations

import logging
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.errors import ValidationError
from app.models import Analysis, MLModel, MLRun
from app.repositories.dataset_repo import get_dataset_for_user, load_dataset_df
from app.schemas import MLRequest, StatsRequest
from app.services import ml as ml_service
from app.services import stats as stats_service

logger = logging.getLogger("nexus")

router = APIRouter(prefix="/api/statistics", tags=["statistics"])


@router.get("/descriptive")
def descriptive(dataset_id: str, columns: str = "",
                user=Depends(get_current_user), db: Session = Depends(get_db)):
    ds = get_dataset_for_user(db, dataset_id, user.id)
    df = load_dataset_df(ds)
    cols = [c for c in columns.split(",") if c] or None
    return {"result": stats_service.descriptive(df, cols)}


@router.get("/correlation")
def correlation(dataset_id: str, columns: str = "", method: str = "pearson",
                user=Depends(get_current_user), db: Session = Depends(get_db)):
    ds = get_dataset_for_user(db, dataset_id, user.id)
    df = load_dataset_df(ds)
    if not columns:
        cols = [str(c) for c in df.columns if df[c].dtype.kind in "fi"][:8]
    else:
        cols = [c for c in columns.split(",") if c][:10]
    return {"result": stats_service.correlation(df, cols, method)}


@router.post("/test")
def run_test(dataset_id: str, payload: StatsRequest,
             user=Depends(get_current_user), db: Session = Depends(get_db)):
    ds = get_dataset_for_user(db, dataset_id, user.id)
    df = load_dataset_df(ds)
    try:
        result = stats_service.run_test(payload.test, df, payload.params)
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc
    analysis = Analysis(dataset_id=ds.id, kind=payload.test, config=payload.params, result=result)
    db.add(analysis)
    db.commit()
    db.refresh(analysis)
    return {"result": result, "analysis_id": analysis.id}


@router.get("/linear-regression")
def lr(dataset_id: str, target: str, features: str = "",
       user=Depends(get_current_user), db: Session = Depends(get_db)):
    ds = get_dataset_for_user(db, dataset_id, user.id)
    df = load_dataset_df(ds)
    feats = [c for c in features.split(",") if c]
    if not feats:
        feats = [str(c) for c in df.columns if c != target and df[c].dtype.kind in "fi"][:4]
    try:
        result = stats_service.linear_regression(df, target, feats)
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc
    return {"result": result}


@router.get("/time-series")
def time_series(dataset_id: str, date_col: str, value_col: str, freq: str = "D", window: int = 7,
                user=Depends(get_current_user), db: Session = Depends(get_db)):
    ds = get_dataset_for_user(db, dataset_id, user.id)
    df = load_dataset_df(ds)
    try:
        result = stats_service.time_series(df, date_col, value_col, freq, window)
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc
    return {"result": result}


@router.get("/history")
def history(dataset_id: str, user=Depends(get_current_user), db: Session = Depends(get_db)):
    analyses = db.query(Analysis).filter(Analysis.dataset_id == dataset_id).order_by(Analysis.created_at.desc()).limit(50).all()
    return {"analyses": [{"id": a.id, "kind": a.kind, "created_at": a.created_at.isoformat() if a.created_at else None} for a in analyses]}


ML_ROUTER = APIRouter(prefix="/api/ml", tags=["machine-learning"])


@ML_ROUTER.post("/train")
def train(dataset_id: str, payload: MLRequest,
          user=Depends(get_current_user), db: Session = Depends(get_db)):
    ds = get_dataset_for_user(db, dataset_id, user.id)
    df = load_dataset_df(ds)
    try:
        result = ml_service.run_ml(df, target=payload.target, features=payload.features,
                                   task=payload.task, algorithms=payload.algorithms,
                                   test_size=payload.test_size)
    except ValidationError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise ValidationError(f"Training failed: {str(exc)[:400]}") from exc

    model = MLModel(dataset_id=ds.id, name=f"Model on {payload.target}", task=result["task"],
                    target=payload.target, metrics=result.get("best_metrics", {}),
                    feature_importance=result.get("feature_importance", []),
                    path="auto")
    db.add(model)
    db.commit()
    db.refresh(model)
    try:
        run_metrics = result.get("models", [])
        for r in run_metrics:
            db.add(MLRun(model_id=model.id, algorithm=r.get("algorithm", ""), metrics=r.get("metrics", {}),
                         config={"target": payload.target}, duration_ms=r.get("duration_ms", 0)))
        db.commit()
    except Exception as e:
        logger.warning("Failed to save ML runs: %s", e)
    return {"result": result, "model_id": model.id}


@ML_ROUTER.get("/models")
def models(dataset_id: str | None = None, user=Depends(get_current_user), db: Session = Depends(get_db)):
    q = db.query(MLModel).order_by(MLModel.created_at.desc())
    if dataset_id:
        q = q.filter(MLModel.dataset_id == dataset_id)
    models = q.limit(100).all()
    return {"models": [{"id": m.id, "name": m.name, "task": m.task, "target": m.target,
                        "metrics": m.metrics, "feature_importance": m.feature_importance[:10],
                        "dataset_id": m.dataset_id,
                        "created_at": m.created_at.isoformat() if m.created_at else None} for m in models]}


@ML_ROUTER.get("/tasks")
def tasks_info():
    return {"tasks": {k: {"models": v["models"], "metrics": v["metrics"]} for k, v in ml_service.TASKS.items()}}