import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ProjectCreate(BaseModel):
    domain: str
    brand_name: str | None = None
    is_competitor_only: bool = False


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


class AiVisibilityProviderOut(BaseModel):
    provider: str
    configured: bool
    status: str | None = None
    cited: bool | None = None
    position: int | None = None
    error_message: str | None = None
    checked_at: datetime | None = None


class AiVisibilityOut(BaseModel):
    query_text: str | None = None
    providers: list[AiVisibilityProviderOut] = []


class AuditOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    status: str
    created_at: datetime
    completed_at: datetime | None
    results: list[AuditResultOut] = []
    ai_visibility: AiVisibilityOut | None = None


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


class AuditCompareOut(BaseModel):
    audit_a: AuditOut
    audit_b: AuditOut
    diff_by_tool: dict[str, dict | None]


class AuditShareOut(BaseModel):
    share_token: str
    share_url: str


class ScanCreate(BaseModel):
    domain: str


class ScanResultItem(BaseModel):
    tool: str
    status: str
    score: int | None
    findings: list


class ScanOut(BaseModel):
    domain: str
    results: list[ScanResultItem]


class ApiKeyCreate(BaseModel):
    name: str


class ApiKeyCreated(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    key_prefix: str
    key: str  # raw key -- present only on the create response, never again
    created_at: datetime


class ApiKeyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    key_prefix: str
    created_at: datetime
    last_used_at: datetime | None
