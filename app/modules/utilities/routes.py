"""Utilities API routes — meter readings & utility costs."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import Optional
from app.database import get_db
from app.auth.dependencies import get_current_user
from app.auth.models import UserAccount
from app.modules.utilities.models import UtilityReading

router = APIRouter(prefix="/api/utilities", tags=["Utilities"])


def _reading_dict(r):
    return {c.name: getattr(r, c.name) for c in r.__table__.columns}


@router.get("")
def list_readings(
    utility_type: Optional[str] = None,
    status: Optional[str] = None,
    property_id: Optional[int] = None,
    unit_id: Optional[int] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    q = db.query(UtilityReading)
    if user.tenant_org_id:
        q = q.filter(UtilityReading.tenant_org_id == user.tenant_org_id)
    if utility_type:
        q = q.filter(UtilityReading.utility_type == utility_type)
    if status:
        q = q.filter(UtilityReading.status == status)
    if property_id:
        q = q.filter(UtilityReading.property_id == property_id)
    if unit_id:
        q = q.filter(UtilityReading.unit_id == unit_id)
    if search:
        q = q.filter(or_(
            UtilityReading.meter_number.ilike(f"%{search}%"),
            UtilityReading.utility_type.ilike(f"%{search}%"),
        ))
    items = q.order_by(UtilityReading.reading_date.desc()).all()
    return {"total": len(items), "items": [_reading_dict(r) for r in items]}


@router.get("/{reading_id}")
def get_reading(reading_id: int, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    r = db.query(UtilityReading).filter(UtilityReading.id == reading_id).first()
    if not r:
        raise HTTPException(404, "Reading not found")
    return _reading_dict(r)


@router.post("", status_code=201)
def create_reading(data: dict, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    r = UtilityReading(**{k: v for k, v in data.items() if hasattr(UtilityReading, k)})
    if user.tenant_org_id:
        r.tenant_org_id = user.tenant_org_id
    # Auto-calculate usage and total_cost
    if r.current_reading and r.previous_reading:
        r.usage = float(r.current_reading) - float(r.previous_reading)
    if r.usage and r.rate_per_unit:
        r.total_cost = float(r.usage) * float(r.rate_per_unit)
    db.add(r)
    db.commit()
    db.refresh(r)
    return _reading_dict(r)


@router.put("/{reading_id}")
def update_reading(reading_id: int, data: dict, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    r = db.query(UtilityReading).filter(UtilityReading.id == reading_id).first()
    if not r:
        raise HTTPException(404, "Reading not found")
    for k, v in data.items():
        if hasattr(r, k) and k not in ("id", "created_at"):
            setattr(r, k, v)
    # Recalculate
    if r.current_reading and r.previous_reading:
        r.usage = float(r.current_reading) - float(r.previous_reading)
    if r.usage and r.rate_per_unit:
        r.total_cost = float(r.usage) * float(r.rate_per_unit)
    db.commit()
    db.refresh(r)
    return _reading_dict(r)


@router.delete("/{reading_id}")
def delete_reading(reading_id: int, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    r = db.query(UtilityReading).filter(UtilityReading.id == reading_id).first()
    if not r:
        raise HTTPException(404, "Reading not found")
    db.delete(r)
    db.commit()
    return {"message": "Reading deleted"}
