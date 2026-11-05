"""Calendar aggregation endpoint: per-day hours for selected users."""
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..service import get_default_daily_hours, instance_dict
from .users import _to_saved

router = APIRouter()


@router.get("", response_model=schemas.CalendarResponse)
def get_calendar(
    start: str = Query(..., description="YYYY-MM-DD"),
    end: str = Query(..., description="YYYY-MM-DD"),
    instance_id: Optional[int] = Query(None, description="Limit to one instance"),
    db: Session = Depends(get_db),
):
    try:
        start_dt = datetime.strptime(start, "%Y-%m-%d")
        end_dt = datetime.strptime(end, "%Y-%m-%d")
    except ValueError:
        from fastapi import HTTPException

        raise HTTPException(status_code=422, detail="Invalid date range")

    target_hours = get_default_daily_hours(db)

    user_query = (
        db.query(models.User)
        .join(models.Instance)
        .filter(models.User.selected, models.Instance.enabled)
    )
    if instance_id is not None:
        user_query = user_query.filter(models.User.instance_id == instance_id)
    selected_users = user_query.order_by(models.Instance.id, models.User.display_name).all()
    selected_user_ids = [u.id for u in selected_users]
    all_instances = db.query(models.Instance).filter(models.Instance.enabled).order_by(models.Instance.id).all()
    instances = {i.id: i for i in all_instances}

    # Aggregate seconds per user per day
    rows = (
        db.query(
            models.User.id,
            func.date(models.Worklog.worklog_date).label("day"),
            func.sum(models.Worklog.seconds).label("total_seconds"),
        )
        .join(
            models.User,
            (models.User.instance_id == models.Worklog.instance_id)
            & (models.User.user_key == models.Worklog.user_key),
        )
        .filter(
            models.User.id.in_(selected_user_ids or [-1]),
            models.Worklog.worklog_date >= start_dt,
            models.Worklog.worklog_date <= end_dt + timedelta(days=1) - timedelta(seconds=1),
        )
        .group_by(models.User.id, "day")
        .all()
    )

    per_day: dict[str, int] = {}
    per_user: dict[int, dict[str, int]] = {}
    for uid, day, seconds in rows:
        # SQLite returns 'YYYY-MM-DD'; other databases return a date object.
        day = day if isinstance(day, str) else day.strftime("%Y-%m-%d")
        seconds = int(seconds or 0)
        per_day[day] = per_day.get(day, 0) + seconds
        per_user.setdefault(uid, {})[day] = seconds

    def _status(seconds: int, target: float) -> tuple[float, str]:
        hours = round(seconds / 3600.0, 2)
        if seconds == 0:
            return hours, "none"
        if hours < target * 0.95:
            return hours, "under"
        if hours <= target * 1.05:
            return hours, "ok"
        return hours, "over"

    # The consolidated row sums every selected user, so its target does too.
    combined_target = target_hours * max(len(selected_users), 1)

    user_calendars: list[schemas.UserCalendar] = []
    for u in selected_users:
        udays = []
        for day in sorted(per_user.get(u.id, {})):
            secs = per_user[u.id][day]
            hours, status = _status(secs, target_hours)
            udays.append(
                schemas.WorklogDay(date=day, seconds=secs, hours=hours, target_hours=target_hours, status=status)
            )
        user_calendars.append(
            schemas.UserCalendar(
                user=_to_saved(u),
                instance_name=instances[u.instance_id].name,
                total_hours=round(sum(d.seconds for d in udays) / 3600.0, 2),
                days=udays,
            )
        )

    days: list[schemas.WorklogDay] = []
    cursor = start_dt
    while cursor <= end_dt:
        day_str = cursor.strftime("%Y-%m-%d")
        seconds = per_day.get(day_str, 0)
        hours, status = _status(seconds, combined_target)
        days.append(
            schemas.WorklogDay(
                date=day_str,
                seconds=seconds,
                hours=hours,
                target_hours=combined_target,
                status=status,
            )
        )
        cursor += timedelta(days=1)

    total_hours = round(sum(d.seconds for d in days) / 3600.0, 2)

    return schemas.CalendarResponse(
        daily_target_hours=target_hours,
        days=days,
        users=user_calendars,
        total_hours=total_hours,
        selected_users=[_to_saved(u) for u in selected_users],
        instances=[instance_dict(inst) for inst in all_instances],
    )
