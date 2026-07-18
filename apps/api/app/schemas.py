import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ProjectCreate(BaseModel):
    domain: str


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    domain: str
    created_at: datetime


class AuditCreate(BaseModel):
    project_id: uuid.UUID


class AuditResultOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    tool: str
    status: str
    score: int | None
    findings: list
    raw: dict
    progress: dict | None = None
    diff: dict | None = None
    created_at: datetime


class AuditOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    status: str
    created_at: datetime
    completed_at: datetime | None
    results: list[AuditResultOut] = []


class AuditSummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: str
    created_at: datetime
    completed_at: datetime | None
