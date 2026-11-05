"""Application configuration endpoints (daily target hours, etc.)."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db

router = APIRouter()


@router.get("")
def get_config(db: Session = Depends(get_db)):
    """Return all config as a dict (key -> value)."""
    entries = db.query(models.ConfigEntry).all()
    return {e.key: e.value for e in entries}


@router.put("")
def update_config(payload: schemas.ConfigUpdate, db: Session = Depends(get_db)):
    if payload.key == "daily_target_hours":
        try:
            ok = 0 < float(payload.value) <= 24
        except ValueError:
            ok = False
        if not ok:
            raise HTTPException(status_code=422, detail="daily_target_hours must be a number between 0 and 24.")
    entry = db.query(models.ConfigEntry).filter(models.ConfigEntry.key == payload.key).first()
    if entry:
        entry.value = payload.value
    else:
        db.add(models.ConfigEntry(key=payload.key, value=payload.value))
    db.commit()
    return {payload.key: payload.value}
