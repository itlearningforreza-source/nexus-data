from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import (
    String, Integer, Float, Boolean, DateTime, Text, JSON, ForeignKey, func
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def uuid_str() -> str:
    return uuid.uuid4().hex


class TimestampMixin:
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime, default=dt.datetime.utcnow, index=True
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime, default=dt.datetime.utcnow, onupdate=dt.datetime.utcnow
    )


# ── Organization / Workspace ──────────────────────────────────────────────
class Organization(Base, TimestampMixin):
    __tablename__ = "organizations"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uuid_str)
    name: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(100), unique=True)

    users = relationship("OrganizationUser", back_populates="organization", cascade="all, delete-orphan")


class OrganizationUser(Base):
    __tablename__ = "organization_users"

    organization_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("organizations.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    role: Mapped[str] = mapped_column(String(20), default="owner")

    organization = relationship("Organization", back_populates="users")
    user = relationship("User", back_populates="organizations")


class Workspace(Base, TimestampMixin):
    __tablename__ = "workspaces"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uuid_str)
    name: Mapped[str] = mapped_column(String(200))
    organization_id: Mapped[str] = mapped_column(String(32), ForeignKey("organizations.id", ondelete="CASCADE"))


# ── User ──────────────────────────────────────────────────────────────────
class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    password_hash: Mapped[str] = mapped_column(String(500))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    avatar_color: Mapped[str] = mapped_column(String(20), default="#0A84FF")
    last_login: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)

    organizations = relationship("OrganizationUser", back_populates="user", cascade="all, delete-orphan")


class Project(Base, TimestampMixin):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uuid_str)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    owner_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    organization_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)
    is_favorite: Mapped[bool] = mapped_column(Boolean, default=False)

    datasets = relationship("Dataset", back_populates="project", cascade="all, delete-orphan")


# ── Dataset ───────────────────────────────────────────────────────────────
class Dataset(Base, TimestampMixin):
    __tablename__ = "datasets"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uuid_str)
    project_id: Mapped[str] = mapped_column(String(32), ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_type: Mapped[str] = mapped_column(String(30), default="csv")
    original_filename: Mapped[str] = mapped_column(String(300), default="")
    file_id: Mapped[str] = mapped_column(String(64), unique=True)
    format: Mapped[str] = mapped_column(String(20), default="table")
    version: Mapped[int] = mapped_column(Integer, default=1)
    row_count: Mapped[int] = mapped_column(Integer, default=0)
    column_count: Mapped[int] = mapped_column(Integer, default=0)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    quality_score: Mapped[float] = mapped_column(Float, default=100.0)
    tags: Mapped[list] = mapped_column(JSON, default=list)
    owner_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    is_favorite: Mapped[bool] = mapped_column(Boolean, default=False)

    project = relationship("Project", back_populates="datasets")
    versions = relationship("DatasetVersion", back_populates="dataset", cascade="all, delete-orphan")
    columns = relationship("DatasetColumn", back_populates="dataset", cascade="all, delete-orphan")


class DatasetVersion(Base, TimestampMixin):
    __tablename__ = "dataset_versions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uuid_str)
    dataset_id: Mapped[str] = mapped_column(String(32), ForeignKey("datasets.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    file_id: Mapped[str] = mapped_column(String(64))
    row_count: Mapped[int] = mapped_column(Integer, default=0)
    column_count: Mapped[int] = mapped_column(Integer, default=0)
    change_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    dataset = relationship("Dataset", back_populates="versions")


class DatasetColumn(Base, TimestampMixin):
    __tablename__ = "dataset_columns"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uuid_str)
    dataset_id: Mapped[str] = mapped_column(String(32), ForeignKey("datasets.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    index: Mapped[int] = mapped_column(Integer)
    data_type: Mapped[str] = mapped_column(String(30), default="unknown")
    semantic_type: Mapped[str] = mapped_column(String(30), default="raw")
    nullable: Mapped[bool] = mapped_column(Boolean, default=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    dataset = relationship("Dataset", back_populates="columns")


class Transformation(Base, TimestampMixin):
    __tablename__ = "transformations"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uuid_str)
    dataset_id: Mapped[str] = mapped_column(String(32), ForeignKey("datasets.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    steps: Mapped[list] = mapped_column(JSON, default=list)
    version_after: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_by_id: Mapped[int | None] = mapped_column(Integer, nullable=True)


class Pipeline(Base, TimestampMixin):
    __tablename__ = "pipelines"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uuid_str)
    project_id: Mapped[str] = mapped_column(String(32), ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    nodes: Mapped[list] = mapped_column(JSON, default=list)
    edges: Mapped[list] = mapped_column(JSON, default=list)
    version: Mapped[int] = mapped_column(Integer, default=1)


# ── SQL ───────────────────────────────────────────────────────────────────
class Query(Base, TimestampMixin):
    __tablename__ = "queries"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uuid_str)
    project_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("projects.id", ondelete="CASCADE"), nullable=True, index=True)
    dataset_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("datasets.id", ondelete="CASCADE"), nullable=True)
    sql: Mapped[str] = mapped_column(Text)
    is_saved: Mapped[bool] = mapped_column(Boolean, default=False)
    name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    execution_time_ms: Mapped[float] = mapped_column(Float, default=0.0)
    row_count: Mapped[int] = mapped_column(Integer, default=0)


# ── Charts / Dashboards ───────────────────────────────────────────────────
class Chart(Base, TimestampMixin):
    __tablename__ = "charts"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uuid_str)
    project_id: Mapped[str] = mapped_column(String(32), ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    dataset_id: Mapped[str] = mapped_column(String(32), ForeignKey("datasets.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(200))
    chart_type: Mapped[str] = mapped_column(String(50), default="bar")
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    is_favorite: Mapped[bool] = mapped_column(Boolean, default=False)


class Dashboard(Base, TimestampMixin):
    __tablename__ = "dashboards"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uuid_str)
    project_id: Mapped[str] = mapped_column(String(32), ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    layout: Mapped[list] = mapped_column(JSON, default=list)
    version: Mapped[int] = mapped_column(Integer, default=1)
    is_favorite: Mapped[bool] = mapped_column(Boolean, default=False)


class DashboardElement(Base, TimestampMixin):
    __tablename__ = "dashboard_elements"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uuid_str)
    dashboard_id: Mapped[str] = mapped_column(String(32), ForeignKey("dashboards.id", ondelete="CASCADE"), index=True)
    element_type: Mapped[str] = mapped_column(String(30))  # chart, kpi, table, text, image, slicer, metric
    position: Mapped[dict] = mapped_column(JSON, default=dict)
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    is_locked: Mapped[bool] = mapped_column(Boolean, default=False)
    is_hidden: Mapped[bool] = mapped_column(Boolean, default=False)


# ── Statistics / ML ───────────────────────────────────────────────────────
class Analysis(Base, TimestampMixin):
    __tablename__ = "analyses"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uuid_str)
    dataset_id: Mapped[str] = mapped_column(String(32), ForeignKey("datasets.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(50))  # descriptive, correlation, ttest, anova...
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    created_by_id: Mapped[int | None] = mapped_column(Integer, nullable=True)


class MLModel(Base, TimestampMixin):
    __tablename__ = "ml_models"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uuid_str)
    dataset_id: Mapped[str] = mapped_column(String(32), ForeignKey("datasets.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    task: Mapped[str] = mapped_column(String(30))  # regression, classification, clustering, anomaly
    target: Mapped[str] = mapped_column(String(200))
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    feature_importance: Mapped[list] = mapped_column(JSON, default=list)
    path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_favorite: Mapped[bool] = mapped_column(Boolean, default=False)


class MLRun(Base, TimestampMixin):
    __tablename__ = "ml_runs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uuid_str)
    model_id: Mapped[str] = mapped_column(String(32), ForeignKey("ml_models.id", ondelete="CASCADE"), index=True)
    algorithm: Mapped[str] = mapped_column(String(100))
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    duration_ms: Mapped[float] = mapped_column(Float, default=0.0)


# ── Notebook ──────────────────────────────────────────────────────────────
class Notebook(Base, TimestampMixin):
    __tablename__ = "notebooks"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uuid_str)
    project_id: Mapped[str] = mapped_column(String(32), ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    cells: Mapped[list] = mapped_column(JSON, default=list)
    version: Mapped[int] = mapped_column(Integer, default=1)
    is_favorite: Mapped[bool] = mapped_column(Boolean, default=False)


class NotebookCell(Base, TimestampMixin):
    __tablename__ = "notebook_cells"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uuid_str)
    notebook_id: Mapped[str] = mapped_column(String(32), ForeignKey("notebooks.id", ondelete="CASCADE"), index=True)
    cell_type: Mapped[str] = mapped_column(String(20))  # code, markdown
    source: Mapped[Text] = mapped_column(Text, default="")
    output: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    execution_count: Mapped[int] = mapped_column(Integer, default=0)


# ── Reports ───────────────────────────────────────────────────────────────
class Report(Base, TimestampMixin):
    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uuid_str)
    project_id: Mapped[str] = mapped_column(String(32), ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    sections: Mapped[list] = mapped_column(JSON, default=list)
    template: Mapped[str] = mapped_column(String(50), default="blank")
    version: Mapped[int] = mapped_column(Integer, default=1)
    is_favorite: Mapped[bool] = mapped_column(Boolean, default=False)


class ReportElement(Base, TimestampMixin):
    __tablename__ = "report_elements"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uuid_str)
    report_id: Mapped[str] = mapped_column(String(32), ForeignKey("reports.id", ondelete="CASCADE"), index=True)
    element_type: Mapped[str] = mapped_column(String(30))
    position: Mapped[int] = mapped_column(Integer)
    config: Mapped[dict] = mapped_column(JSON, default=dict)


# ── AI ────────────────────────────────────────────────────────────────────
class AIConversation(Base, TimestampMixin):
    __tablename__ = "ai_conversations"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uuid_str)
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    project_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    title: Mapped[str] = mapped_column(String(200), default="New Analysis")


class AIMessage(Base, TimestampMixin):
    __tablename__ = "ai_messages"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uuid_str)
    conversation_id: Mapped[str] = mapped_column(String(32), ForeignKey("ai_conversations.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(20))  # user, assistant
    content: Mapped[Text] = mapped_column(Text, default="")
    artifacts: Mapped[list] = mapped_column(JSON, default=list)


# ── Audit / Jobs / Favorites / Snippets ───────────────────────────────────
class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    organization_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    action: Mapped[str] = mapped_column(String(100), index=True)
    resource: Mapped[str] = mapped_column(String(100))
    resource_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow, index=True)


class Job(Base, TimestampMixin):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uuid_str)
    name: Mapped[str] = mapped_column(String(200))
    task: Mapped[str] = mapped_column(String(100))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="queued", index=True)
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    organization_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    started_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)


class JobStatus:
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Favorite(Base):
    __tablename__ = "favorites"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True)
    resource_type: Mapped[str] = mapped_column(String(30))
    resource_id: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)


class SQLSnippet(Base, TimestampMixin):
    __tablename__ = "sql_snippets"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uuid_str)
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    name: Mapped[str] = mapped_column(String(200))
    sql: Mapped[Text] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)


class HistoryEntry(Base, TimestampMixin):
    __tablename__ = "history_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(Integer, index=True)
    project_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    action: Mapped[str] = mapped_column(String(100))
    resource: Mapped[str] = mapped_column(String(50))
    resource_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    label: Mapped[str] = mapped_column(String(300), default="")
    detail: Mapped[dict] = mapped_column(JSON, default=dict)