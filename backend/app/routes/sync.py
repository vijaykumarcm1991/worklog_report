"""Sync trigger endpoints."""
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import schemas
from ..database import get_db
from ..service import sync_all

router = APIRouter()


@router.post("", response_model=schemas.SyncResult)
def trigger_sync(payload: Optional[schemas.SyncRequest] = None, db: Session = Depends(get_db)):
    instance_ids = payload.instance_ids if payload else None
    return sync_all(db, instance_ids)
