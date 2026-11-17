from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.errors import NotFoundError
from app.models import Notebook
from app.repositories.dataset_repo import get_dataset_for_user, load_dataset_df
from app.schemas import CellUpload, NotebookCreate, NotebookUpdate
from app.services import notebook as nb

router = APIRouter(prefix="/api/notebooks", tags=["notebooks"])


@router.get("")
def list_notebooks(user=Depends(get_current_user), db: Session = Depends(get_db)):
    books = db.query(Notebook).order_by(Notebook.updated_at.desc()).all()
    return {"notebooks": [_n(b) for b in books]}


@router.post("")
def create_notebook(payload: NotebookCreate, user=Depends(get_current_user), db: Session = Depends(get_db)):
    b = Notebook(project_id=payload.project_id, name=payload.name.strip(),
                 cells=[
                     {"type": "markdown", "source": "## Welcome\n\nRun Python to analyse your dataset. `df` is preloaded when a dataset is attached."}
                 ])
    db.add(b)
    db.commit()
    db.refresh(b)
    return {"notebook": _n(b)}


@router.get("/{notebook_id}")
def get_notebook(notebook_id: str, user=Depends(get_current_user), db: Session = Depends(get_db)):
    b = db.query(Notebook).filter(Notebook.id == notebook_id).first()
    if not b:
        raise NotFoundError("Notebook not found.")
    return {"notebook": _n(b)}


@router.patch("/{notebook_id}")
def update_notebook(notebook_id: str, payload: NotebookUpdate,
                    user=Depends(get_current_user), db: Session = Depends(get_db)):
    b = db.query(Notebook).filter(Notebook.id == notebook_id).first()
    if not b:
        raise NotFoundError("Notebook not found.")
    if payload.name is not None:
        b.name = payload.name.strip()
    if payload.cells is not None:
        b.cells = payload.cells
        b.version += 1
    db.commit()
    db.refresh(b)
    return {"notebook": _n(b)}


@router.delete("/{notebook_id}")
def delete_notebook(notebook_id: str, user=Depends(get_current_user), db: Session = Depends(get_db)):
    b = db.query(Notebook).filter(Notebook.id == notebook_id).first()
    if not b:
        raise NotFoundError("Notebook not found.")
    db.delete(b)
    db.commit()
    return {"ok": True}


@router.post("/run-cell")
def run_cell(payload: CellUpload, user=Depends(get_current_user), db: Session = Depends(get_db)):
    dataset = None
    if payload.dataset_id:
        ds = get_dataset_for_user(db, payload.dataset_id, user.id)
        dataset = load_dataset_df(ds)
    result = nb.execute_cell(payload.code, dataset)
    return {"output": result}


def _n(nb_: Notebook) -> dict:
    return {
        "id": nb_.id, "name": nb_.name, "cells": nb_.cells, "project_id": nb_.project_id,
        "version": nb_.version, "is_favorite": nb_.is_favorite,
        "created_at": nb_.created_at.isoformat() if nb_.created_at else None,
        "updated_at": nb_.updated_at.isoformat() if nb_.updated_at else None,
    }