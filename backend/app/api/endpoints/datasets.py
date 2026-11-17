from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.errors import DataProcessingError, NotFoundError, ValidationError
from app.models import (
    Dataset, DatasetColumn, DatasetVersion, Transformation,
)
from app.repositories.dataset_repo import (
    dataset_dict, get_dataset_for_user, load_dataset_df,
)
from app.schemas import CleanRequest, DatasetUpdate, TransformRequest
from app.services import profile as profile_service
from app.services import quality as quality_service
from app.services.cleaning import apply_clean_operation
from app.services.datastore import (
    data_profile_cache_key,
    parse_file,
    read_cache,
    save_canonical,
    store_incoming,
    validate_upload,
    write_cache,
)
from app.services.demo import demo_dataset, loads_demo
from app.services.pipeline import run_pipeline
from app.services.profile import profile_dataframe

router = APIRouter(prefix="/api/datasets", tags=["datasets"])


@router.post("/upload")
async def upload_dataset(
    file: UploadFile = File(...),
    project_id: str = Form(...),
    description: str | None = Form(None),
    name: str | None = Form(None),
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    content = await file.read()
    safe_name, ext, store_id = validate_upload(file.filename or "dataset", content)
    store_incoming(content, store_id)
    # parse immediately to validate
    from app.services.datastore import original_path
    try:
        df = parse_file(original_path(store_id), ext)
    except DataProcessingError as exc:
        original_path(store_id).unlink(missing_ok=True)
        raise exc

    file_id = uuid.uuid4().hex
    save_canonical(df, file_id)
    ds_name = name or (Path(safe_name).stem.replace("_", " ").replace("-", " ").title()[:200])
    ds = Dataset(
        project_id=project_id,
        name=ds_name,
        description=description,
        source_type=ext.lstrip("."),
        original_filename=safe_name,
        file_id=file_id,
        format="table",
        version=1,
        row_count=len(df),
        column_count=len(df.columns),
        size_bytes=len(content),
        tags=[],
        owner_id=user.id,
    )
    db.add(ds)
    db.commit()
    db.refresh(ds)

    for i, c in enumerate(df.columns):
        dt = str(df[c].dtype)
        db.add(DatasetColumn(dataset_id=ds.id, name=str(c), index=i, data_type=_dtype_str(dt)))
    db.add(DatasetVersion(dataset_id=ds.id, version=1, file_id=file_id,
                          row_count=len(df), column_count=len(df.columns), created_by_id=user.id))
    db.commit()

    prof = profile_dataframe(df)
    q = quality_service.quality_issues(df)
    ds.quality_score = q["score"]
    db.commit()
    return {"dataset": dataset_dict(ds), "preview": _preview(df, 50)}


@router.post("/import-demo")
def import_demo(payload: __import__("app.schemas", fromlist=["DemoImport"]).DemoImport,
                user=Depends(get_current_user), db: Session = Depends(get_db)):
    if payload.name not in loads_demo():
        raise ValidationError(f"Unknown demo dataset '{payload.name}'. Available: {', '.join(loads_demo())}")
    df = demo_dataset(payload.name)
    file_id = uuid.uuid4().hex
    save_canonical(df, file_id)
    ds = Dataset(
        project_id=payload.project_id,
        name=payload.name.replace("_", " ").title(),
        description=f"Demo dataset: {payload.name}",
        source_type="demo",
        original_filename=f"{payload.name}.csv",
        file_id=file_id,
        format="table",
        version=1,
        row_count=len(df),
        column_count=len(df.columns),
        size_bytes=int(df.memory_usage(deep=True).sum()),
        tags=["demo"],
        owner_id=user.id,
    )
    db.add(ds)
    db.commit()
    db.refresh(ds)
    for i, c in enumerate(df.columns):
        db.add(DatasetColumn(dataset_id=ds.id, name=str(c), index=i, data_type=_dtype_str(str(df[c].dtype))))
    db.add(DatasetVersion(dataset_id=ds.id, version=1, file_id=file_id,
                          row_count=len(df), column_count=len(df.columns), created_by_id=user.id))
    db.commit()
    q = quality_service.quality_issues(df)
    ds.quality_score = q["score"]
    db.commit()
    return {"dataset": dataset_dict(ds)}


@router.get("/demo-list")
def list_demo(user=Depends(get_current_user)):
    return {"datasets": loads_demo()}


@router.get("")
def list_datasets(user=Depends(get_current_user), db: Session = Depends(get_db)):
    datasets = db.query(Dataset).order_by(Dataset.created_at.desc()).all()
    return {"datasets": [dataset_dict(d) for d in datasets]}


@router.get("/{dataset_id}")
def get_dataset(dataset_id: str, user=Depends(get_current_user), db: Session = Depends(get_db)):
    ds = get_dataset_for_user(db, dataset_id, user.id)
    columns = db.query(DatasetColumn).filter(DatasetColumn.dataset_id == ds.id).order_by(DatasetColumn.index).all()
    return {"dataset": {**dataset_dict(ds), "columns": [
        {"id": c.id, "name": c.name, "index": c.index, "data_type": c.data_type, "nullable": c.nullable}
        for c in columns
    ]}}


@router.delete("/{dataset_id}")
def delete_dataset(dataset_id: str, user=Depends(get_current_user), db: Session = Depends(get_db)):
    ds = get_dataset_for_user(db, dataset_id, user.id)
    db.delete(ds)
    db.commit()
    return {"ok": True}


@router.patch("/{dataset_id}")
def update_dataset(dataset_id: str, payload: DatasetUpdate, user=Depends(get_current_user), db: Session = Depends(get_db)):
    ds = get_dataset_for_user(db, dataset_id, user.id)
    if payload.name is not None:
        ds.name = payload.name.strip()
    if payload.description is not None:
        ds.description = payload.description
    if payload.tags is not None:
        ds.tags = payload.tags
    if payload.is_favorite is not None:
        ds.is_favorite = payload.is_favorite
    db.commit()
    db.refresh(ds)
    return {"dataset": dataset_dict(ds)}


@router.post("/{dataset_id}/preview")
def preview_dataset(dataset_id: str, body: dict | None = None,
                    user=Depends(get_current_user), db: Session = Depends(get_db)):
    ds = get_dataset_for_user(db, dataset_id, user.id)
    df = load_dataset_df(ds)
    start = (body or {}).get("start", 0)
    limit = min(int((body or {}).get("limit", 100)), 500)
    return _preview(df, limit, start=start)


@router.get("/{dataset_id}/profile")
def dataset_profile(dataset_id: str, refresh: bool = False,
                    user=Depends(get_current_user), db: Session = Depends(get_db)):
    ds = get_dataset_for_user(db, dataset_id, user.id)
    cache = data_profile_cache_key(dataset_id, ds.version)
    if refresh is False and cache.exists():
        from app.services.datastore import read_cache
        cached = read_cache(cache)
        if cached:
            return cached
    df = load_dataset_df(ds)
    prof = profile_dataframe(df)
    q = quality_service.quality_issues(df)
    ds.quality_score = q["score"]
    db.commit()
    result = {"profile": prof, "quality": q, "dataset": dataset_dict(ds)}
    write_cache(cache, result)
    return result


@router.post("/{dataset_id}/clean")
def clean_dataset(dataset_id: str, payload: CleanRequest,
                  user=Depends(get_current_user), db: Session = Depends(get_db)):
    ds = get_dataset_for_user(db, dataset_id, user.id)
    df = load_dataset_df(ds)
    for op in payload.operations:
        df = apply_clean_operation(df, op.get("op"), op.get("params", {}))
    _commit_version(df, ds, db, user, note=payload.note or f"Cleaning: {', '.join(o['op'] for o in payload.operations[:5])}")
    prof = profile_dataframe(df)
    q = quality_service.quality_issues(df)
    ds.quality_score = q["score"]
    db.commit()
    return {"dataset": dataset_dict(ds), "preview": _preview(df, 50), "quality": q}


@router.post("/{dataset_id}/transform")
def transform_dataset(dataset_id: str, payload: TransformRequest,
                      user=Depends(get_current_user), db: Session = Depends(get_db)):
    ds = get_dataset_for_user(db, dataset_id, user.id)
    df = load_dataset_df(ds)
    try:
        df = run_pipeline(df, payload.steps)
    except Exception as exc:  # noqa: BLE001
        if isinstance(exc, ValidationError):
            raise exc
        raise DataProcessingError("The transformation could not be applied.",
                                  detail={"error": str(exc)}) from exc
    _commit_version(df, ds, db, user, note=payload.note or "Transformation pipeline")
    tr = Transformation(dataset_id=ds.id, steps=payload.steps, version_after=ds.version, name=payload.note or "Pipeline run")
    db.add(tr)
    db.commit()
    prof = profile_dataframe(df)
    q = quality_service.quality_issues(df)
    ds.quality_score = q["score"]
    db.commit()
    return {"dataset": dataset_dict(ds), "preview": _preview(df, 50), "quality": q, "transformation_id": tr.id}


@router.get("/{dataset_id}/versions")
def dataset_versions(dataset_id: str, user=Depends(get_current_user), db: Session = Depends(get_db)):
    ds = get_dataset_for_user(db, dataset_id, user.id)
    versions = db.query(DatasetVersion).filter(DatasetVersion.dataset_id == ds.id).order_by(DatasetVersion.version.desc()).all()
    return {"versions": [
        {"id": v.id, "version": v.version, "row_count": v.row_count, "column_count": v.column_count,
         "change_note": v.change_note, "created_at": v.created_at.isoformat() if v.created_at else None}
        for v in versions
    ]}


@router.post("/{dataset_id}/restore/{version_id}")
def restore_version(dataset_id: str, version_id: str,
                    user=Depends(get_current_user), db: Session = Depends(get_db)):
    ds = get_dataset_for_user(db, dataset_id, user.id)
    v = db.query(DatasetVersion).filter(DatasetVersion.id == version_id, DatasetVersion.dataset_id == ds.id).first()
    if not v:
        raise NotFoundError("Version not found.")
    from app.services.datastore import load_canonical
    df = load_canonical(v.file_id)
    new_id = uuid.uuid4().hex
    save_canonical(df, new_id)
    next_version = ds.version + 1
    ds.file_id = new_id
    ds.version = next_version
    ds.row_count = len(df)
    ds.column_count = len(df.columns)
    db.add(DatasetVersion(dataset_id=ds.id, version=next_version, file_id=new_id,
                          row_count=len(df), column_count=len(df.columns),
                          change_note=f"Restored from version {v.version}", created_by_id=user.id))
    db.commit()
    return {"dataset": dataset_dict(ds), "preview": _preview(df, 50)}


def _commit_version(df, ds, db, user, note: str):
    new_id = uuid.uuid4().hex
    save_canonical(df, new_id)
    next_version = ds.version + 1
    ds.file_id = new_id
    ds.version = next_version
    ds.row_count = len(df)
    ds.column_count = len(df.columns)
    ds.size_bytes = 0
    for old_col in db.query(DatasetColumn).filter(DatasetColumn.dataset_id == ds.id).all():
        db.delete(old_col)
    for i, c in enumerate(df.columns):
        db.add(DatasetColumn(dataset_id=ds.id, name=str(c), index=i, data_type=_dtype_str(str(df[c].dtype))))
    db.add(DatasetVersion(dataset_id=ds.id, version=next_version, file_id=new_id,
                          row_count=len(df), column_count=len(df.columns),
                          change_note=note, created_by_id=user.id))
    _invalidate_cache(ds.id, next_version)
    db.commit()


def _invalidate_cache(dataset_id: str, version: int):
    for cache_version in range(0, version):
        p = data_profile_cache_key(dataset_id, cache_version)
        if p.exists():
            p.unlink()


def _dtype_str(dt: str) -> str:
    if dt.startswith("int"):
        return "integer"
    if dt.startswith("float"):
        return "float"
    if dt.startswith("bool"):
        return "boolean"
    if "datetime" in dt or "timestamp" in dt:
        return "datetime"
    if dt == "category":
        return "categorical"
    return "object"


def _preview(df, limit: int, start: int = 0) -> dict:
    import pandas as pd
    sub = df.iloc[start:start + limit]
    return {
        "columns": [str(c) for c in df.columns],
        "rows": sub.where(pd.notna(sub), None).values.tolist(),
        "row_count": int(len(df)),
        "truncated": int(len(df)) > start + limit,
    }