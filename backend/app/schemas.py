"""Pydantic schemas for API request/response."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------------- Instances ----------------


class InstanceBase(BaseModel):
    name: str
    instance_type: str = Field(..., pattern="^(cloud|onprem)$")
    base_url: str
    username: str
    label: str = ""
    days_to_fetch: int = 30
    enabled: bool = True


class InstanceCreate(InstanceBase):
    token: str


class InstanceUpdate(BaseModel):
    name: Optional[str] = None
    instance_type: Optional[str] = None
    base_url: Optional[str] = None
    username: Optional[str] = None
    token: Optional[str] = None
    label: Optional[str] = None
    days_to_fetch: Optional[int] = None
    enabled: Optional[bool] = None


class InstanceRead(InstanceBase):
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
