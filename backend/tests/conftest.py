"""Shared pytest fixtures. Sets required env before importing the app."""
import os
import tempfile

_tmpdir = tempfile.mkdtemp(prefix="worklog_test_")
os.environ.setdefault(
    "WORKLOG_ENC_KEY", "FSc3Lo_LYYZLteaHPyfjdtzlIQdVzxEf0nvopIeI19E="
)
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_tmpdir}/test.db")
os.environ.setdefault("SYNC_INTERVAL_MINUTES", "0")

import pytest  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402

from app.database import SessionLocal, engine, init_db  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client():
    init_db()
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def db():
    session = SessionLocal()
    yield session
    session.close()
