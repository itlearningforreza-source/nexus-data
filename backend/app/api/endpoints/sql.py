from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.errors import NotFoundError
from app.models import Query, SQLSnippet
from app.repositories.dataset_repo import get_dataset_for_user, load_dataset_df
from app.schemas import SQLRequest
from app.services import sql_engine

router = APIRouter(prefix="/api/sql", tags=["sql"])


@router.post("/run")
def run_sql(payload: SQLRequest, user=Depends(get_current_user), db: Session = Depends(get_db)):
    tables = {}
    for ds_id in payload.dataset_ids:
        ds = get_dataset_for_user(db, ds_id, user.id)
        df = load_dataset_df(ds)
        tables[ds.name] = df
        tables[ds.id] = df
    result = sql_engine.execute_sql(payload.sql, tables, limit=payload.limit)
    out = result.to_dict()
    if payload.save and payload.project_id:
        q = Query(project_id=payload.project_id, dataset_id=payload.dataset_ids[0] if payload.dataset_ids else None,
                  sql=payload.sql, is_saved=True, name=payload.save_name or "Untitled query",
                  user_id=user.id, execution_time_ms=out["execution_time_ms"], row_count=out["row_count"])
        db.add(q)
        db.commit()
        db.refresh(q)
        out["query_id"] = q.id
    return out


@router.get("/schema")
def sql_schema(user=Depends(get_current_user), db: Session = Depends(get_db)):
    from app.models import Dataset, DatasetColumn
    datasets = db.query(Dataset).all()
    out = []
    for ds in datasets:
        cols = db.query(DatasetColumn).filter(DatasetColumn.dataset_id == ds.id).order_by(DatasetColumn.index).all()
        out.append({
            "dataset_id": ds.id,
            "name": ds.name,
            "table_name": ds.name,
            "columns": [{"name": c.name, "type": c.data_type} for c in cols],
            "row_count": ds.row_count,
        })
    return {"tables": out}


@router.get("/queries")
def saved_queries(user=Depends(get_current_user), db: Session = Depends(get_db)):
    queries = db.query(Query).filter(Query.is_saved == True).order_by(Query.updated_at.desc()).limit(200).all()
    return {"queries": [_q(q) for q in queries]}


@router.get("/history")
def query_history(user=Depends(get_current_user), db: Session = Depends(get_db)):
    queries = db.query(Query).filter(Query.is_saved == False).order_by(Query.updated_at.desc()).limit(200).all()
    return {"queries": [_q(q) for q in queries]}


@router.post("/snapshot")
def snapshot_query(payload: SQLRequest, user=Depends(get_current_user), db: Session = Depends(get_db)):
    q = Query(project_id=payload.project_id, sql=payload.sql, is_saved=False,
              user_id=user.id, name=payload.save_name)
    db.add(q)
    db.commit()
    db.refresh(q)
    return {"query": _q(q)}


@router.get("/snippets")
def snippets(user=Depends(get_current_user), db: Session = Depends(get_db)):
    snips = db.query(SQLSnippet).limit(100).all()
    return {"snippets": [{"id": s.id, "name": s.name, "sql": s.sql, "description": s.description} for s in snips]}


def _q(q: Query) -> dict:
    return {
        "id": q.id, "sql": q.sql, "name": q.name, "is_saved": q.is_saved,
        "project_id": q.project_id, "dataset_id": q.dataset_id,
        "execution_time_ms": q.execution_time_ms, "row_count": q.row_count,
        "created_at": q.created_at.isoformat() if q.created_at else None,
        "updated_at": q.updated_at.isoformat() if q.updated_at else None,
    }