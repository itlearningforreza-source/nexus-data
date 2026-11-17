from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models import User
from app.schemas import ProjectCreate, ProjectUpdate
from app.models import Project
from app.core.errors import NotFoundError

router = APIRouter(prefix="/api/users", tags=["users"])


class UserUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    avatar_color: str | None = None


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return {"user": _u(user)}


@router.patch("/me")
def update_me(payload: UserUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if payload.name:
        user.name = payload.name.strip()
    if payload.avatar_color:
        user.avatar_color = payload.avatar_color
    db.commit()
    db.refresh(user)
    return {"user": _u(user)}


def _u(u: User) -> dict:
    return {"id": u.id, "email": u.email, "name": u.name, "avatar_color": u.avatar_color,
            "created_at": u.created_at.isoformat() if u.created_at else None}


@router.get("/projects")
def list_user_projects(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    projects = db.query(Project).filter(Project.is_archived == False).all()
    return {"projects": [_p(p) for p in projects]}


@router.post("/projects")
def create_project(payload: ProjectCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = Project(name=payload.name.strip(), description=payload.description, owner_id=user.id)
    db.add(p)
    db.commit()
    db.refresh(p)
    return {"project": _p(p)}


def _p(p: Project) -> dict:
    return {
        "id": p.id, "name": p.name, "description": p.description,
        "owner_id": p.owner_id, "is_archived": p.is_archived, "is_favorite": p.is_favorite,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }