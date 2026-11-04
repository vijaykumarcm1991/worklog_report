"""API integration tests (mocked storage only; no live Jira)."""
from datetime import datetime, timedelta, timezone

from app import models
from app.database import SessionLocal


def test_health(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_instance_crud_and_credential_hidden(client):
    # Create
    resp = client.post(
        "/api/instances",
        json={
            "name": "Cloud",
            "instance_type": "cloud",
            "base_url": "https://acme.atlassian.net",
            "username": "dev@acme.com",
            "token": "ATATT3-SUPER-SECRET",
            "label": "#6C8EFF",
            "days_to_fetch": 14,
        },
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["has_credential"] is True
    assert "token" not in data
    assert "SUPER-SECRET" not in resp.text
    inst_id = data["id"]

    # List
    resp = client.get("/api/instances")
    assert resp.status_code == 200
    assert len(resp.json()) == 1

    # Update name + token
    resp = client.put(
        f"/api/instances/{inst_id}",
        json={"name": "Cloud Renamed", "token": "NEW-TOKEN"},
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Cloud Renamed"
    assert "NEW-TOKEN" not in resp.text

    # Delete
    resp = client.delete(f"/api/instances/{inst_id}")
    assert resp.status_code == 204
    assert client.get("/api/instances").json() == []


def test_daily_target_config_roundtrip(client):
    client.put("/api/config", json={"key": "daily_target_hours", "value": "6.5"})
    cfg = client.get("/api/config").json()
    assert cfg["daily_target_hours"] == "6.5"


def test_calendar_empty_with_selected_default(client):
    # No instances/users: calendar should return an empty but valid body.
    start = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    end = datetime.now().strftime("%Y-%m-%d")
    resp = client.get(f"/api/calendar?start={start}&end={end}")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "days" in body
    assert "daily_target_hours" in body
    assert body["total_hours"] == 0.0


def test_worklog_aggregation_in_calendar(client, db):
    # Seed an instance + user + worklog directly, then check calendar groups it.
    inst = models.Instance(
        name="Agg",
        instance_type="cloud",
        base_url="https://acme.atlassian.net",
        username="dev@acme.com",
        token_enc="encrypted-dummy",
        label="",
        days_to_fetch=30,
        enabled=True,
    )
    db.add(inst)
    db.flush()
    user = models.User(
        instance_id=inst.id,
        user_key="account-id-1",
        display_name="Dev One",
        selected=True,
    )
    db.add(user)
    db.flush()
    day = datetime.now().replace(hour=12, minute=0, second=0, microsecond=0)
    db.add(
        models.Worklog(
            instance_id=inst.id,
            user_key="account-id-1",
            worklog_id="1000",
            worklog_date=day,
            seconds=28800,  # 8 hours
            comment="built features",
            issue_key="ACME-1",
        )
    )
    db.commit()

    client.put("/api/config", json={"key": "daily_target_hours", "value": "8"})
    start = (day - timedelta(days=1)).strftime("%Y-%m-%d")
    end = (day + timedelta(days=1)).strftime("%Y-%m-%d")
    resp = client.get(f"/api/calendar?start={start}&end={end}")
    assert resp.status_code == 200
    body = resp.json()
    day_str = day.strftime("%Y-%m-%d")
    target = next(d for d in body["days"] if d["date"] == day_str)
    assert target["seconds"] == 28800
    assert target["status"] == "ok"


def test_calendar_per_user_and_instance_filter(client, db):
    day = datetime(2026, 3, 10, 12, 0, 0)
    insts = []
    for name in ("PerUserA", "PerUserB"):
        inst = models.Instance(name=name, instance_type="cloud", base_url="https://x.atlassian.net", username="u", token_enc="x")
        db.add(inst)
        db.flush()
        user = models.User(instance_id=inst.id, user_key=f"k-{name}", display_name=f"User {name}", selected=True)
        db.add(user)
        db.add(models.Worklog(instance_id=inst.id, user_key=user.user_key, worklog_id="1", worklog_date=day,
                              seconds=3600 if name == "PerUserA" else 7200))
        insts.append(inst)
    db.commit()

    body = client.get("/api/calendar?start=2026-03-01&end=2026-03-31").json()
    mine = {u["user"]["display_name"]: u for u in body["users"] if u["user"]["display_name"].startswith("User PerUser")}
    assert mine["User PerUserA"]["days"][0]["hours"] == 1.0
    assert mine["User PerUserB"]["days"][0]["hours"] == 2.0
    assert next(d for d in body["days"] if d["date"] == "2026-03-10")["hours"] == 3.0  # consolidated

    only_b = client.get(f"/api/calendar?start=2026-03-01&end=2026-03-31&instance_id={insts[1].id}").json()
    assert [u["user"]["display_name"] for u in only_b["users"]] == ["User PerUserB"]
    assert next(d for d in only_b["days"] if d["date"] == "2026-03-10")["hours"] == 2.0
