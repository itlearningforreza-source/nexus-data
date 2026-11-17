from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.errors import ForbiddenError, NotFoundError
from app.models import Dataset, Project
from app.services.datastore import load_canonical
from app.core.database import SessionLocal


def get_project_for_user(db: Session, project_id: str, user_id: int | None) -> Project:
    project = db.query(Project).filter(Project.id == project_id, Project.is_archived == False).first()
    if not project:
        raise NotFoundError("Project not found.")
    if project.owner_id and user_id and project.owner_id != user_id:
        raise ForbiddenError("You do not have access to this project.")
    return project


def get_dataset_for_user(db: Session, dataset_id: str, user_id: int | None) -> Dataset:
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise NotFoundError("Dataset not found.")
    project = db.query(Project).filter(Project.id == dataset.project_id).first()
    if project and project.owner_id and user_id and project.owner_id != user_id:
        raise ForbiddenError("You do not have access to this dataset.")
    return dataset


def load_dataset_df(dataset: Dataset):
    return load_canonical(dataset.file_id)


def dataset_dict(dataset: Dataset) -> dict:
    return {
        "id": dataset.id,
        "project_id": dataset.project_id,
        "name": dataset.name,
        "description": dataset.description,
        "source_type": dataset.source_type,
        "original_filename": dataset.original_filename,
        "format": dataset.format,
        "version": dataset.version,
        "row_count": dataset.row_count,
        "column_count": dataset.column_count,
        "size_bytes": dataset.size_bytes,
        "quality_score": dataset.quality_score,
        "tags": dataset.tags or [],
        "is_favorite": dataset.is_favorite,
        "created_at": dataset.created_at.isoformat() if dataset.created_at else None,
        "updated_at": dataset.updated_at.isoformat() if dataset.updated_at else None,
    }