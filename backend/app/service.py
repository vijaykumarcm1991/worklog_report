"""Business logic: syncing worklogs from Jira instances into the local DB.

All times are IST wall-clock (see timeutil); nothing is converted.
"""
from __future__ import annotations

import logging
import threading
from datetime import timedelta
from typing import Optional

from sqlalchemy.orm import Session

from . import models
from .config import get_settings
from .crypto import decrypt
from .jira import make_client
from .timeutil import today_ist_start

logger = logging.getLogger("worklog.service")

# One sync at a time: the scheduler and the manual "Sync" button would
# otherwise race on the same rows.
_sync_lock = threading.Lock()


def instance_dict(inst: models.Instance) -> dict:
    return {
        "id": inst.id,
        "name": inst.name,
        "instance_type": inst.instance_type,
        "base_url": inst.base_url,
        "username": inst.username,
        "label": inst.label,
        "days_to_fetch": inst.days_to_fetch,
        "enabled": inst.enabled,
        "has_credential": bool(inst.token_enc),
        "created_at": inst.created_at,
    }


def get_default_daily_hours(db: Session) -> float:
    entry = db.query(models.ConfigEntry).filter(models.ConfigEntry.key == "daily_target_hours").first()
    if entry and entry.value:
        try:
            hours = float(entry.value)
            if hours > 0:
                return hours
        except ValueError:
            pass
    return get_settings().default_daily_hours


def ensure_default_config(db: Session) -> None:
    """Seed daily_target_hours from settings if it has never been set."""
    exists = db.query(models.ConfigEntry).filter(models.ConfigEntry.key == "daily_target_hours").first()
    if not exists:
        db.add(models.ConfigEntry(key="daily_target_hours", value=str(get_settings().default_daily_hours)))
        db.commit()


def sync_instance(db: Session, inst: models.Instance) -> tuple[int, list[str]]:
    """Fetch and store worklogs for the selected users of one instance.

    Returns (number of worklogs stored, per-user error messages).
    """
    try:
        token = decrypt(inst.token_enc)
    except Exception:  # noqa: BLE001
        logger.warning("Cannot decrypt credential for instance %s", inst.name)
        return 0, [f"{inst.name}: cannot decrypt stored credential (check WORKLOG_ENC_KEY)"]

    client = make_client(inst, token)
    # Whole days: from IST midnight N days ago through today.
    since = today_ist_start() - timedelta(days=inst.days_to_fetch or 30)

    users = db.query(models.User).filter(models.User.instance_id == inst.id, models.User.selected).all()
    count = 0
    user_errors: list[str] = []
    for user in users:
        try:
            raw = client.fetch_worklogs(user.user_key, since)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Worklog fetch failed for %s / %s: %s", inst.name, user.user_key, exc)
            user_errors.append(f"{inst.name} · {user.display_name}: {exc}")
            continue

        # De-duplicate by worklog id (an issue can come back twice while paging).
        fetched = {wl["worklog_id"]: wl for wl in raw if wl["worklog_id"]}

        try:
            existing = {
                w.worklog_id: w
                for w in db.query(models.Worklog).filter(
                    models.Worklog.instance_id == inst.id,
                    models.Worklog.user_key == user.user_key,
                )
            }
            for wl_id, wl in fetched.items():
                row = existing.get(wl_id)
                if row:
                    row.worklog_date = wl["worklog_date"]
                    row.issue_key = wl["issue_key"]
                    row.seconds = wl["seconds"]
                    row.comment = wl["comment"]
                else:
                    db.add(
                        models.Worklog(
                            instance_id=inst.id,
                            user_key=user.user_key,
                            worklog_id=wl_id,
                            worklog_date=wl["worklog_date"],
                            seconds=wl["seconds"],
                            comment=wl["comment"],
                            issue_key=wl["issue_key"],
                        )
                    )
            # Anything we hold inside the fetched window that Jira no longer
            # returns was deleted (or moved out of the window) in Jira.
            for wl_id, row in existing.items():
                if wl_id not in fetched and row.worklog_date >= since:
                    db.delete(row)
            db.commit()
            count += len(fetched)
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            logger.exception("Storing worklogs failed for %s / %s", inst.name, user.user_key)
            user_errors.append(f"{inst.name} · {user.display_name}: could not store worklogs ({exc})")
    return count, user_errors


def sync_all(db: Session, instance_ids: Optional[list[int]] = None) -> dict:
    """Sync selected instances. Returns aggregate result dict."""
    with _sync_lock:
        query = db.query(models.Instance).filter(models.Instance.enabled)
        if instance_ids:
            query = query.filter(models.Instance.id.in_(instance_ids))

        instances = query.all()
        total_worklogs = 0
        errors: list[str] = []
        synced_instances = 0
        total_users = 0
        for inst in instances:
            name = inst.name
            try:
                total_users += (
                    db.query(models.User)
                    .filter(models.User.instance_id == inst.id, models.User.selected)
                    .count()
                )
                n, user_errors = sync_instance(db, inst)
                total_worklogs += n
                synced_instances += 1
                errors.extend(user_errors)
            except Exception as exc:  # noqa: BLE001
                db.rollback()
                errors.append(f"{name}: {exc}")
        return {
            "instances": synced_instances,
            "users": total_users,
            "worklogs": total_worklogs,
            "errors": errors,
        }
