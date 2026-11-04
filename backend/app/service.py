"""Business logic: syncing worklogs from Jira instances into the local DB."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from . import models
from .crypto import decrypt
from .jira import JiraAuthError, make_client

logger = logging.getLogger("worklog.service")


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
            return float(entry.value)
        except ValueError:
            pass
    return 8.0


def set_daily_hours(db: Session, hours: float) -> None:
    entry = db.query(models.ConfigEntry).filter(models.ConfigEntry.key == "daily_target_hours").first()
    if entry:
        entry.value = str(hours)
    else:
        db.add(models.ConfigEntry(key="daily_target_hours", value=str(hours)))
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
    since = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=inst.days_to_fetch or 30)

    users = db.query(models.User).filter(models.User.instance_id == inst.id, models.User.selected).all()
    count = 0
    user_errors: list[str] = []
    for user in users:
        try:
            raw = client.fetch_worklogs(user.user_key, since)
        except JiraAuthError as exc:
            logger.warning("Worklog fetch failed for %s / %s: %s", inst.name, user.user_key, exc)
            user_errors.append(f"{inst.name} · {user.display_name}: {exc}")
            continue
        except Exception as exc:  # noqa: BLE001
            logger.warning("Worklog fetch failed for %s / %s: %s", inst.name, user.user_key, exc)
            user_errors.append(f"{inst.name} · {user.display_name}: {exc}")
            continue
        for wl in raw:
            existing = (
                db.query(models.Worklog)
                .filter(
                    models.Worklog.instance_id == inst.id,
                    models.Worklog.user_key == user.user_key,
                    models.Worklog.worklog_id == wl["worklog_id"],
                )
                .first()
            )
            if existing:
                existing.worklog_date = wl["worklog_date"]
                existing.issue_key = wl["issue_key"]
                existing.seconds = wl["seconds"]
                existing.comment = wl["comment"]
            else:
                db.add(
                    models.Worklog(
                        instance_id=inst.id,
                        user_key=user.user_key,
                        worklog_id=wl["worklog_id"],
                        worklog_date=wl["worklog_date"],
                        seconds=wl["seconds"],
                        comment=wl["comment"],
                        issue_key=wl["issue_key"],
                    )
                )
            count += 1
    db.commit()
    return count, user_errors


def sync_all(db: Session, instance_ids: Optional[list[int]] = None) -> dict:
    """Sync selected instances. Returns aggregate result dict."""
    query = db.query(models.Instance).filter(models.Instance.enabled)
    if instance_ids:
        query = query.filter(models.Instance.id.in_(instance_ids))

    instances = query.all()
    total_worklogs = 0
    errors: list[str] = []
    synced_instances = 0
    total_users = 0
    for inst in instances:
        try:
            total_users += len(
                db.query(models.User).filter(models.User.instance_id == inst.id, models.User.selected).all()
            )
        except Exception:  # noqa: BLE001
            pass
        try:
            n, user_errors = sync_instance(db, inst)
            total_worklogs += n
            synced_instances += 1
            errors.extend(user_errors)
        except JiraAuthError as exc:
            errors.append(f"{inst.name}: {exc}")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{inst.name}: {exc}")
    return {
        "instances": synced_instances,
        "users": total_users,
        "worklogs": total_worklogs,
        "errors": errors,
    }
