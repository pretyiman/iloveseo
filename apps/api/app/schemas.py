import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ProjectCreate(BaseModel):
    domain: str
    brand_name: str | None = None


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    domain: str
    brand_name: str | None
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


class TrackedQueryCreate(BaseModel):
    query_text: str
    competitor_domains: list[str] = []


class TrackedQueryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    query_text: str
    competitor_domains: list
    active: bool
    created_at: datetime


class GeoCheckOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tracked_query_id: uuid.UUID
    provider: str
    status: str
    cited: bool | None
    position: int | None
    competitor_mentions: dict
    citation_urls: list
    response_text: str | None
    error_message: str | None
    created_at: datetime
