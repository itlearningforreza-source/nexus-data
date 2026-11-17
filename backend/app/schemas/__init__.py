from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, EmailStr, Field


class AuthRegister(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    email: EmailStr
    password: str = Field(min_length=8, max_length=200)


class AuthLogin(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict[str, Any]


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    is_archived: bool | None = None
    is_favorite: bool | None = None


class DatasetCreate(BaseModel):
    project_id: str
    name: str | None = None
    description: str | None = None
    tags: list[str] = []


class DatasetUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    tags: list[str] | None = None
    is_favorite: bool | None = None


class PreviewRequest(BaseModel):
    file_id: str


class ImportConfig(BaseModel):
    dataset_id: str | None = None
    sheet: int | str | None = None
    delimiter: str | None = None
    encoding: str | None = None
    has_header: bool | None = None
    name: str | None = None


class CleanRequest(BaseModel):
    operations: list[dict[str, Any]]
    note: str | None = None


class TransformRequest(BaseModel):
    steps: list[dict[str, Any]]
    note: str | None = None


class SQLRequest(BaseModel):
    sql: str
    dataset_ids: list[str] = Field(default_factory=list)
    save: bool = False
    save_name: str | None = None
    project_id: str | None = None
    limit: int = 5000


class ChartRequest(BaseModel):
    chart_type: str
    config: dict[str, Any] = Field(default_factory=dict)
    name: str = "Chart"
    save: bool = False


class DashboardCreate(BaseModel):
    project_id: str
    name: str
    description: str | None = None


class DashboardUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    layout: list[dict[str, Any]] | None = None


class StatsRequest(BaseModel):
    test: str
    params: dict[str, Any] = Field(default_factory=dict)


class MLRequest(BaseModel):
    target: str
    features: list[str] | None = None
    task: str | None = None
    algorithms: list[str] | None = None
    test_size: float = 0.25


class NotebookCreate(BaseModel):
    project_id: str | None = None
    name: str = "Untitled notebook"


class NotebookUpdate(BaseModel):
    name: str | None = None
    cells: list[dict[str, Any]] | None = None


class CellUpload(BaseModel):
    code: str
    dataset_id: str | None = None


class AIAsk(BaseModel):
    message: str
    dataset_id: str
    conversation_id: str | None = None


class ReportCreate(BaseModel):
    project_id: str
    name: str
    description: str | None = None
    template: str = "blank"


class ReportUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    sections: list[dict[str, Any]] | None = None
    template: str | None = None


class ExportRequest(BaseModel):
    format: str = "csv"
    dataset_id: str | None = None
    query_id: str | None = None
    sql: str | None = None
    project_id: str | None = None
    limit: int = 100000


class DemoImport(BaseModel):
    name: str
    project_id: str


class SearchQuery(BaseModel):
    q: str


class Message(BaseModel):
    message: str
    error_id: str | None = None
    detail: dict[str, Any] = Field(default_factory=dict)