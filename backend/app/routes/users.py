"""User search, save, list and selection per instance."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from .. import models, schemas
from ..crypto import decrypt
from ..database import get_db
from ..jira import make_client

router = APIRouter()


def _get_instance_or_404(db: Session, instance_id: int) -> models.Instance:
    inst = db.query(models.Instance).filter(models.Instance.id == instance_id).first()
    if not inst:
        raise HTTPException(status_code=404, detail="Instance not found")
    return inst


def _to_saved(u: models.User) -> schemas.UserSaved:
    return schemas.UserSaved(
        id=u.id,
        instance_id=u.instance_id,
        user_key=u.user_key,
        display_name=u.display_name,
        email=u.email,
        avatar_url=u.avatar_url,
        selected=u.selected,
    )


@router.get("", response_model=list[schemas.UserSaved])
def list_users(instance_id: int, db: Session = Depends(get_db)):
    _get_instance_or_404(db, instance_id)
    users = (
        db.query(models.User)
        .filter(models.User.instance_id == instance_id)
        .order_by(models.User.display_name)
        .all()
    )
    return [_to_saved(u) for u in users]


@router.get("/search", response_model=list[schemas.UserSearchItem])
def search_users(
    instance_id: int,
    q: str = Query("", description="Search query (empty for all)"),
    db: Session = Depends(get_db),
):
    inst = _get_instance_or_404(db, instance_id)
    try:
        token = decrypt(inst.token_enc)
    except Exception:  # noqa: BLE001
        raise HTTPException(status_code=400, detail="No stored credential to search users with.")
    client = make_client(inst, token)
    try:
        results = client.search_users(q, max_results=25)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"User search failed: {exc}")
    return results


@router.post("", response_model=schemas.UserSaved, status_code=201)
def save_user(instance_id: int, payload: schemas.UserSearchItem, db: Session = Depends(get_db)):
    """Save a user (from a search result) to the instance."""
    _get_instance_or_404(db, instance_id)
    existing = (
        db.query(models.User)
        .filter(
            models.User.instance_id == instance_id,
            models.User.user_key == payload.user_key,
        )
        .first()
    )
    if existing:
        existing.display_name = payload.display_name
        existing.email = payload.email
        existing.avatar_url = payload.avatar_url
        db.commit()
        db.refresh(existing)
        return _to_saved(existing)
    user = models.User(
        instance_id=instance_id,
        user_key=payload.user_key,
        display_name=payload.display_name,
        email=payload.email,
        avatar_url=payload.avatar_url,
        selected=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return _to_saved(user)


@router.put("/{user_id}", response_model=schemas.UserSaved)
def update_user(
    instance_id: int,
    user_id: int,
    payload: Optional[schemas.UserSelectRequest] = None,
    db: Session = Depends(get_db),
):
    user = db.query(models.User).filter(models.User.id == user_id, models.User.instance_id == instance_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if payload is not None and payload.selected is not None:
        user.selected = payload.selected
    else:
        user.selected = not user.selected
    db.commit()
    db.refresh(user)
    return _to_saved(user)


@router.delete("/{user_id}", status_code=204)
def delete_user(instance_id: int, user_id: int, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == user_id, models.User.instance_id == instance_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    db.query(models.Worklog).filter(
        models.Worklog.instance_id == instance_id,
        models.Worklog.user_key == user.user_key,
    ).delete(synchronize_session=False)
    db.delete(user)
    db.commit()
