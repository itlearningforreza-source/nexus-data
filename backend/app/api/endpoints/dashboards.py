from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.errors import NotFoundError
from app.models import Dashboard
from app.schemas import DashboardCreate, DashboardUpdate

router = APIRouter(prefix="/api/dashboards", tags=["dashboards"])


@router.get("")
def list_dashboards(user=Depends(get_current_user), db: Session = Depends(get_db)):
    dashboards = db.query(Dashboard).order_by(Dashboard.updated_at.desc()).all()
    return {"dashboards": [_d(d) for d in dashboards]}


@router.post("")
def create_dashboard(payload: DashboardCreate, user=Depends(get_current_user), db: Session = Depends(get_db)):
    d = Dashboard(project_id=payload.project_id, name=payload.name.strip(), description=payload.description,
                  layout=[])
    db.add(d)
    db.commit()
    db.refresh(d)
    return {"dashboard": _d(d)}


@router.get("/{dashboard_id}")
def get_dashboard(dashboard_id: str, user=Depends(get_current_user), db: Session = Depends(get_db)):
    d = db.query(Dashboard).filter(Dashboard.id == dashboard_id).first()
    if not d:
        raise NotFoundError("Dashboard not found.")
    return {"dashboard": _d(d)}


@router.patch("/{dashboard_id}")
def update_dashboard(dashboard_id: str, payload: DashboardUpdate,
                     user=Depends(get_current_user), db: Session = Depends(get_db)):
    d = db.query(Dashboard).filter(Dashboard.id == dashboard_id).first()
    if not d:
        raise NotFoundError("Dashboard not found.")
    if payload.name is not None:
        d.name = payload.name.strip()
    if payload.description is not None:
        d.description = payload.description
    if payload.layout is not None:
        d.layout = payload.layout
        d.version += 1
    db.commit()
    db.refresh(d)
    return {"dashboard": _d(d)}


@router.delete("/{dashboard_id}")
def delete_dashboard(dashboard_id: str, user=Depends(get_current_user), db: Session = Depends(get_db)):
    d = db.query(Dashboard).filter(Dashboard.id == dashboard_id).first()
    if not d:
        raise NotFoundError("Dashboard not found.")
    db.delete(d)
    db.commit()
    return {"ok": True}


def _d(d: Dashboard) -> dict:
    return {
        "id": d.id, "name": d.name, "description": d.description, "layout": d.layout,
        "project_id": d.project_id, "version": d.version, "is_favorite": d.is_favorite,
        "created_at": d.created_at.isoformat() if d.created_at else None,
        "updated_at": d.updated_at.isoformat() if d.updated_at else None,
    }