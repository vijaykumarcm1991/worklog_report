"""Application configuration endpoints (daily target hours, etc.)."""
from fastapi import APIRouter, Depends
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
    entry = db.query(models.ConfigEntry).filter(models.ConfigEntry.key == payload.key).first()
    if entry:
        entry.value = payload.value
    else:
        db.add(models.ConfigEntry(key=payload.key, value=payload.value))
    db.commit()
    return {payload.key: payload.value}
