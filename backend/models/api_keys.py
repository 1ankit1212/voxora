"""
DubKaro — API Key Models
"""

from pydantic import BaseModel
from typing import Optional


class CreateApiKeyRequest(BaseModel):
    key_name: str = "Default"


class ApiKeyResponse(BaseModel):
    id: str
    key_name: str
    api_key: str  # Only shown once at creation
    plan: str
    tokens_total: int
    tokens_used: int
    rate_limit_per_min: int
    is_active: bool
    created_at: str


class ApiKeyListItem(BaseModel):
    id: str
    key_name: str
    api_key_preview: str  # "dk_...abc" (masked)
    plan: str
    tokens_total: int
    tokens_used: int
    tokens_remaining: int
    rate_limit_per_min: int
    is_active: bool
    last_used_at: Optional[str]
    created_at: str


class UsageLogItem(BaseModel):
    endpoint: str
    tokens_consumed: int
    video_duration_sec: float
    source_lang: str
    target_lang: str
    status: str
    created_at: str