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


# ---------------- regression tests for fixed bugs ----------------


def _seed_instance(db, name):
    inst = models.Instance(name=name, instance_type="cloud", base_url="https://x.atlassian.net",
                           username="u", token_enc="x")
    db.add(inst)
    db.flush()
    db.add(models.User(instance_id=inst.id, user_key=f"k-{name}", display_name=f"User {name}", selected=True))
    db.add(models.Worklog(instance_id=inst.id, user_key=f"k-{name}", worklog_id="1",
                          worklog_date=datetime(2026, 3, 10, 12), seconds=3600))
    db.commit()
    return inst.id


def test_delete_instance_removes_users_and_worklogs_and_ids_not_reused(client, db):
    inst_id = _seed_instance(db, "ToDelete")
    assert client.delete(f"/api/instances/{inst_id}").status_code == 204
    db.expire_all()
    assert db.query(models.User).filter_by(instance_id=inst_id).count() == 0
    assert db.query(models.Worklog).filter_by(instance_id=inst_id).count() == 0

    new = client.post("/api/instances", json={
        "name": "Fresh", "instance_type": "cloud", "base_url": "https://y.atlassian.net",
        "username": "u", "token": "t",
    }).json()
    assert new["id"] != inst_id
    assert client.get(f"/api/instances/{new['id']}/users").json() == []
    client.delete(f"/api/instances/{new['id']}")


def test_delete_user_removes_their_worklogs(client, db):
    inst_id = _seed_instance(db, "UserDel")
    user = db.query(models.User).filter_by(instance_id=inst_id).one()
    assert client.delete(f"/api/instances/{inst_id}/users/{user.id}").status_code == 204
    db.expire_all()
    assert db.query(models.Worklog).filter_by(instance_id=inst_id).count() == 0
    client.delete(f"/api/instances/{inst_id}")


def test_update_instance_rejects_bad_type_and_ignores_nulls(client, db):
    inst_id = _seed_instance(db, "Upd")
    assert client.put(f"/api/instances/{inst_id}", json={"instance_type": "foo"}).status_code == 422
    assert client.put(f"/api/instances/{inst_id}", json={"days_to_fetch": 0}).status_code == 422
    resp = client.put(f"/api/instances/{inst_id}", json={"name": None, "base_url": None})
    assert resp.status_code == 200, resp.text
    assert resp.json()["name"] == "Upd"
    client.delete(f"/api/instances/{inst_id}")


def test_config_rejects_invalid_daily_target(client):
    assert client.put("/api/config", json={"key": "daily_target_hours", "value": "abc"}).status_code == 422
    assert client.put("/api/config", json={"key": "daily_target_hours", "value": "0"}).status_code == 422
    assert client.put("/api/config", json={"key": "daily_target_hours", "value": "8"}).status_code == 200


def test_consolidated_day_target_scales_with_users(client, db):
    a = _seed_instance(db, "ConsA")
    b = _seed_instance(db, "ConsB")
    client.put("/api/config", json={"key": "daily_target_hours", "value": "1"})
    body = client.get(f"/api/calendar?start=2026-03-10&end=2026-03-10&instance_id={a}").json()
    day = body["days"][0]
    assert day["target_hours"] == 1.0 and day["status"] == "ok"
    client.put("/api/config", json={"key": "daily_target_hours", "value": "8"})
    client.delete(f"/api/instances/{a}")
    client.delete(f"/api/instances/{b}")


class _FakeJira:
    def __init__(self, worklogs):
        self.worklogs = worklogs

    def fetch_worklogs(self, user_key, since):
        return list(self.worklogs)


def test_sync_ist_dedupes_and_removes_deleted_worklogs(client, db, monkeypatch):
    from app import service
    from app.crypto import encrypt
    from app.timeutil import today_ist_start

    inst = models.Instance(name="SyncT", instance_type="cloud", base_url="https://s.atlassian.net",
                           username="u", token_enc=encrypt("t"), days_to_fetch=30)
    db.add(inst)
    db.flush()
    db.add(models.User(instance_id=inst.id, user_key="sk", display_name="Sync User", selected=True))
    db.commit()

    today = today_ist_start()
    early = today.replace(hour=2, minute=30)  # 02:30 IST must stay on today
    wl = lambda i, d: {"worklog_id": i, "worklog_date": d, "seconds": 3600, "comment": "", "issue_key": "S-1"}

    fake = _FakeJira([wl("1", early), wl("1", early), wl("2", today.replace(hour=11))])  # "1" duplicated
    monkeypatch.setattr(service, "make_client", lambda inst, token: fake)
    r = client.post("/api/sync", json={"instance_ids": [inst.id]}).json()
    assert r["errors"] == [] and r["worklogs"] == 2

    day = today.strftime("%Y-%m-%d")
    body = client.get(f"/api/calendar?start={day}&end={day}&instance_id={inst.id}").json()
    assert body["days"][0]["seconds"] == 7200

    # Worklog "2" deleted in Jira -> gone after the next sync.
    fake.worklogs = [wl("1", early)]
    client.post("/api/sync", json={"instance_ids": [inst.id]})
    body = client.get(f"/api/calendar?start={day}&end={day}&instance_id={inst.id}").json()
    assert body["days"][0]["seconds"] == 3600
    client.delete(f"/api/instances/{inst.id}")
