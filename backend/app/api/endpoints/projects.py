from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.errors import NotFoundError
from app.models import (
    Project, Dataset, Chart, Dashboard, Notebook, Report, MLModel,
)
from app.schemas import ProjectCreate, ProjectUpdate

router = APIRouter(prefix="/api/projects", tags=["projects"])


def _p(p: Project, counts: dict | None = None) -> dict:
    return {
        "id": p.id, "name": p.name, "description": p.description,
        "owner_id": p.owner_id, "is_archived": p.is_archived, "is_favorite": p.is_favorite,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
        **(counts or {}),
    }


@router.get("")
def list_projects(user=Depends(get_current_user), db: Session = Depends(get_db)):
    projects = db.query(Project).filter(Project.is_archived == False).all()
    out = []
    for p in projects:
        out.append(_p(p, {"counts": {
            "datasets": db.query(Dataset).filter(Dataset.project_id == p.id).count(),
            "charts": db.query(Chart).filter(Chart.project_id == p.id).count(),
            "dashboards": db.query(Dashboard).filter(Dashboard.project_id == p.id).count(),
            "notebooks": db.query(Notebook).filter(Notebook.project_id == p.id).count(),
            "reports": db.query(Report).filter(Report.project_id == p.id).count(),
        }}))
    return {"projects": out}


@router.post("")
def create_project(payload: ProjectCreate, user=Depends(get_current_user), db: Session = Depends(get_db)):
    p = Project(name=payload.name.strip(), description=payload.description, owner_id=user.id)
    db.add(p)
    db.commit()
    db.refresh(p)
    return {"project": _p(p)}


@router.get("/{project_id}")
def get_project(project_id: str, user=Depends(get_current_user), db: Session = Depends(get_db)):
    p = db.query(Project).filter(Project.id == project_id).first()
    if not p:
        raise NotFoundError("Project not found.")
    return {"project": _p(p, {"counts": {
        "datasets": db.query(Dataset).filter(Dataset.project_id == p.id).count(),
        "charts": db.query(Chart).filter(Chart.project_id == p.id).count(),
        "dashboards": db.query(Dashboard).filter(Dashboard.project_id == p.id).count(),
        "notebooks": db.query(Notebook).filter(Notebook.project_id == p.id).count(),
        "reports": db.query(Report).filter(Report.project_id == p.id).count(),
        "models": db.query(MLModel).filter(MLModel.dataset_id.in_(
            db.query(Dataset.id).filter(Dataset.project_id == p.id)
        )).count(),
    }})}


@router.patch("/{project_id}")
def update_project(project_id: str, payload: ProjectUpdate, user=Depends(get_current_user), db: Session = Depends(get_db)):
    p = db.query(Project).filter(Project.id == project_id).first()
    if not p:
        raise NotFoundError("Project not found.")
    for field in ("name", "description", "is_archived", "is_favorite"):
        val = getattr(payload, field, None)
        if val is not None:
            setattr(p, field, val)
    db.commit()
    db.refresh(p)
    return {"project": _p(p)}


@router.delete("/{project_id}")
def delete_project(project_id: str, user=Depends(get_current_user), db: Session = Depends(get_db)):
    p = db.query(Project).filter(Project.id == project_id).first()
    if not p:
        raise NotFoundError("Project not found.")
    db.delete(p)
    db.commit()
    return {"ok": True}


@router.post("/{project_id}/duplicate")
def duplicate_project(project_id: str, user=Depends(get_current_user), db: Session = Depends(get_db)):
    p = db.query(Project).filter(Project.id == project_id).first()
    if not p:
        raise NotFoundError("Project not found.")
    import copy
    np_ = Project(name=p.name + " (copy)", description=p.description, owner_id=p.owner_id)
    db.add(np_)
    db.commit()
    db.refresh(np_)
    for ds in db.query(Dataset).filter(Dataset.project_id == p.id).all():
        import shutil
        from app.services.datastore import canonical_path, save_canonical
        new_id = __import__("uuid").uuid4().hex
        nds = Dataset(project_id=np_.id, name=ds.name, description=ds.description,
                      source_type=ds.source_type, original_filename=ds.original_filename,
                      file_id=new_id, format=ds.format, version=1, row_count=ds.row_count,
                      column_count=ds.column_count, size_bytes=ds.size_bytes, tags=ds.tags)
        df = load_dataset_df(ds)
        save_canonical(df, new_id)
        db.add(nds)
    db.commit()
    return {"project": _p(np_)}


def load_dataset_df(ds: Dataset):
    from app.services.datastore import load_canonical
    return load_canonical(ds.file_id)