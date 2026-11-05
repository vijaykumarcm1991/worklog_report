"""Instance CRUD + connection testing."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..crypto import decrypt, encrypt
from ..database import get_db
from ..jira import JiraAuthError, make_client
from ..service import instance_dict

router = APIRouter()


def _get_instance_or_404(db: Session, instance_id: int) -> models.Instance:
    inst = db.query(models.Instance).filter(models.Instance.id == instance_id).first()
    if not inst:
        raise HTTPException(status_code=404, detail="Instance not found")
    return inst


@router.get("", response_model=list[schemas.InstanceRead])
def list_instances(db: Session = Depends(get_db)):
    return [instance_dict(i) for i in db.query(models.Instance).order_by(models.Instance.id).all()]


@router.post("", response_model=schemas.InstanceRead, status_code=201)
def create_instance(payload: schemas.InstanceCreate, db: Session = Depends(get_db)):
    inst = models.Instance(
        name=payload.name,
        instance_type=payload.instance_type,
        base_url=payload.base_url.rstrip("/"),
        username=payload.username,
        token_enc=encrypt(payload.token),
        label=payload.label,
        days_to_fetch=payload.days_to_fetch,
        enabled=payload.enabled,
    )
    db.add(inst)
    db.commit()
    db.refresh(inst)
    return instance_dict(inst)


@router.get("/{instance_id}", response_model=schemas.InstanceRead)
def get_instance(instance_id: int, db: Session = Depends(get_db)):
    return instance_dict(_get_instance_or_404(db, instance_id))


@router.put("/{instance_id}", response_model=schemas.InstanceRead)
def update_instance(instance_id: int, payload: schemas.InstanceUpdate, db: Session = Depends(get_db)):
    inst = _get_instance_or_404(db, instance_id)
    # Null means "leave unchanged"; it must never blank a required column.
    data = {k: v for k, v in payload.model_dump(exclude_unset=True).items() if v is not None}
    token = data.pop("token", None)
    if token:
        inst.token_enc = encrypt(token)
    for field, value in data.items():
        if field == "base_url":
            value = value.rstrip("/")
        setattr(inst, field, value)
    db.commit()
    db.refresh(inst)
    return instance_dict(inst)


@router.delete("/{instance_id}", status_code=204)
def delete_instance(instance_id: int, db: Session = Depends(get_db)):
    inst = _get_instance_or_404(db, instance_id)
    # Explicit, so nothing is left behind even on databases created before
    # foreign keys were enforced.
    db.query(models.Worklog).filter(models.Worklog.instance_id == instance_id).delete(synchronize_session=False)
    db.query(models.User).filter(models.User.instance_id == instance_id).delete(synchronize_session=False)
    db.delete(inst)
    db.commit()


@router.post("/{instance_id}/test", response_model=schemas.TestResult)
def test_instance(instance_id: int, db: Session = Depends(get_db)):
    inst = _get_instance_or_404(db, instance_id)
    try:
        token = decrypt(inst.token_enc)
    except Exception:  # noqa: BLE001
        raise HTTPException(status_code=400, detail="No stored credential to test with.")
    client = make_client(inst, token)
    ok, message = client.test_connection()
    return schemas.TestResult(
        ok=ok,
        message=message,
        instance_type=inst.instance_type,
        detected_name=message if ok else None,
    )
