"""Pydantic schemas for API request/response."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------------- Instances ----------------


INSTANCE_TYPE_PATTERN = "^(cloud|onprem)$"


class InstanceBase(BaseModel):
    name: str = Field(..., min_length=1)
    instance_type: str = Field(..., pattern=INSTANCE_TYPE_PATTERN)
    base_url: str = Field(..., min_length=1)
    username: str = Field(..., min_length=1)
    label: str = ""
    days_to_fetch: int = Field(30, ge=1, le=365)
    enabled: bool = True


class InstanceCreate(InstanceBase):
    token: str = Field(..., min_length=1)


class InstanceUpdate(BaseModel):
    """Partial update. Fields left out (or sent as null) are not changed."""

    name: Optional[str] = Field(None, min_length=1)
    instance_type: Optional[str] = Field(None, pattern=INSTANCE_TYPE_PATTERN)
    base_url: Optional[str] = Field(None, min_length=1)
    username: Optional[str] = Field(None, min_length=1)
    token: Optional[str] = None
    label: Optional[str] = None
    days_to_fetch: Optional[int] = Field(None, ge=1, le=365)
    enabled: Optional[bool] = None


class InstanceRead(BaseModel):
    # Stored rows are returned as-is, without the create-time constraints.
    name: str
    instance_type: str
    base_url: str
    username: str
    label: Optional[str] = ""
    days_to_fetch: Optional[int] = 30
    enabled: bool = True
    id: int
    # True if a token is stored (never returned itself)
    has_credential: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TestResult(BaseModel):
    ok: bool
    message: str
    instance_type: Optional[str] = None
    detected_name: Optional[str] = None


# ---------------- Users ----------------


class UserSearchItem(BaseModel):
    user_key: str
    display_name: str
    email: str = ""
    avatar_url: str = ""


class UserSaved(BaseModel):
    id: int
    instance_id: int
    user_key: str
    display_name: str
    email: str = ""
    avatar_url: str = ""
    selected: bool

    model_config = ConfigDict(from_attributes=True)


class UserSelectRequest(BaseModel):
    # Explicit selection state; omit to toggle the current value.
    selected: Optional[bool] = None


# ---------------- Config ----------------


class ConfigUpdate(BaseModel):
    key: str
    value: str


# ---------------- Worklogs / Calendar ----------------


class WorklogDay(BaseModel):
    date: str  # YYYY-MM-DD
    seconds: int
    hours: float
    target_hours: float
    status: str  # 'ok' | 'under' | 'over' | 'none'


class UserCalendar(BaseModel):
    """One user's own daily worklog totals (days with no worklogs are omitted)."""

    user: UserSaved
    instance_name: str
    total_hours: float
    days: list[WorklogDay]


class CalendarResponse(BaseModel):
    daily_target_hours: float
    days: list[WorklogDay]  # consolidated across the users in `users`
    users: list[UserCalendar] = []
    total_hours: float
    selected_users: list[UserSaved]
    instances: list[InstanceRead]


class SyncResult(BaseModel):
    instances: int
    users: int
    worklogs: int
    errors: list[str] = []


class SyncRequest(BaseModel):
    instance_ids: Optional[list[int]] = None
