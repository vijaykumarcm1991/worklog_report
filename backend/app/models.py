"""SQLAlchemy models."""
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class Instance(Base):
    """A configured Jira instance (either cloud or on-prem)."""

    __tablename__ = "instances"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    # 'cloud' or 'onprem'
    instance_type = Column(String, nullable=False, default="cloud")
    # For cloud: https://site.atlassian.net ; for onprem: base url e.g. http://jira.corp.local
    base_url = Column(String, nullable=False)
    # Cloud: email ; On-prem: username
    username = Column(String, nullable=False)
    # Encrypted API token / password (Fernet). Stored encrypted; never returned.
    token_enc = Column(Text, nullable=False)
    # Optional label / color used in the UI
    label = Column(String, default="")
    days_to_fetch = Column(Integer, default=30)
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class User(Base):
    """A saved user (a Jira user identity) belonging to an instance."""

    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("instance_id", "user_key", name="uq_user_instance_key"),
    )

    id = Column(Integer, primary_key=True)
    instance_id = Column(Integer, ForeignKey("instances.id", ondelete="CASCADE"), nullable=False)
    # Cloud: accountId ; On-prem: username/key
    user_key = Column(String, nullable=False)
    display_name = Column(String, nullable=False)
    email = Column(String, default="")
    avatar_url = Column(String, default="")
    # Whether this user is selected/active for the calendar
    selected = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Worklog(Base):
    """A cached worklog entry from Jira."""

    __tablename__ = "worklogs"
    __table_args__ = (
        UniqueConstraint("instance_id", "user_key", "worklog_id", name="uq_worklog_id"),
    )

    id = Column(Integer, primary_key=True)
    instance_id = Column(Integer, ForeignKey("instances.id", ondelete="CASCADE"), nullable=False)
    user_key = Column(String, nullable=False)
    worklog_id = Column(String, nullable=False)
    worklog_date = Column(DateTime, nullable=False, index=True)
    seconds = Column(Integer, nullable=False, default=0)
    comment = Column(Text, default="")
    issue_key = Column(String, default="")
    created_at = Column(DateTime, default=datetime.utcnow)


class ConfigEntry(Base):
    """Key/value application configuration."""

    __tablename__ = "config_entries"

    id = Column(Integer, primary_key=True)
    key = Column(String, nullable=False, unique=True)
    value = Column(String, default="")
