"""Utilities API routes — meter readings & utility costs."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import Optional
from datetime import date
from app.database import get_db
from app.auth.dependencies import get_current_user, require_permissions
from app.auth.models import UserAccount
from app.modules.utilities.models import UtilityReading

router = APIRouter(
    prefix="/api/utilities",
    tags=["Utilities"],
    dependencies=[Depends(require_permissions(["utilities", "properties"]))],
)


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
    q = db.query(UtilityReading).filter(UtilityReading.id == reading_id)
    if user.tenant_org_id:
        q = q.filter(UtilityReading.tenant_org_id == user.tenant_org_id)
    r = q.first()
    if not r:
        raise HTTPException(404, "Reading not found")
    return _reading_dict(r)


def _sanitize_reading_data(data: dict) -> dict:
    """Coerce frontend form values to correct types for UtilityReading."""
    clean = {}
    int_fields = {"property_id", "unit_id", "invoice_id"}
    float_fields = {"previous_reading", "current_reading", "usage", "rate_per_unit", "total_cost"}
    date_fields = {"reading_date", "billing_period_start", "billing_period_end"}
    for k, v in data.items():
        if not hasattr(UtilityReading, k) or k in ("id", "created_at"):
            continue
        if v == "" or v is None:
            clean[k] = None
        elif k in int_fields:
            try:
                clean[k] = int(v)
            except (ValueError, TypeError):
                clean[k] = None
        elif k in float_fields:
            try:
                clean[k] = float(v)
            except (ValueError, TypeError):
                clean[k] = 0
        elif k in date_fields:
            if isinstance(v, date):
                clean[k] = v
            elif isinstance(v, str):
                try:
                    clean[k] = date.fromisoformat(v)
                except ValueError:
                    raise HTTPException(400, f"Invalid date for '{k}'. Expected YYYY-MM-DD")
            else:
                raise HTTPException(400, f"Invalid date for '{k}'. Expected YYYY-MM-DD")
        else:
            clean[k] = v
    return clean


@router.post("", status_code=201)
def create_reading(data: dict, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    clean = _sanitize_reading_data(data)
    if not clean.get("utility_type"):
        raise HTTPException(400, "Field 'utility_type' is required")
    if not clean.get("reading_date"):
        raise HTTPException(400, "Field 'reading_date' is required")

    r = UtilityReading(**clean)
    if user.tenant_org_id:
        r.tenant_org_id = user.tenant_org_id
    # Auto-calculate usage and total_cost
    if r.current_reading is not None and r.previous_reading is not None:
        r.usage = float(r.current_reading) - float(r.previous_reading)
    if r.usage is not None and r.rate_per_unit is not None:
        r.total_cost = float(r.usage) * float(r.rate_per_unit)
    db.add(r)
    db.commit()
    db.refresh(r)
    return _reading_dict(r)


@router.put("/{reading_id}")
def update_reading(reading_id: int, data: dict, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    q = db.query(UtilityReading).filter(UtilityReading.id == reading_id)
    if user.tenant_org_id:
        q = q.filter(UtilityReading.tenant_org_id == user.tenant_org_id)
    r = q.first()
    if not r:
        raise HTTPException(404, "Reading not found")
    clean = _sanitize_reading_data(data)
    for k, v in clean.items():
        setattr(r, k, v)
    # Recalculate
    if r.current_reading is not None and r.previous_reading is not None:
        r.usage = float(r.current_reading) - float(r.previous_reading)
    if r.usage is not None and r.rate_per_unit is not None:
        r.total_cost = float(r.usage) * float(r.rate_per_unit)
    db.commit()
    db.refresh(r)
    return _reading_dict(r)


@router.delete("/{reading_id}")
def delete_reading(reading_id: int, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    q = db.query(UtilityReading).filter(UtilityReading.id == reading_id)
    if user.tenant_org_id:
        q = q.filter(UtilityReading.tenant_org_id == user.tenant_org_id)
    r = q.first()
    if not r:
        raise HTTPException(404, "Reading not found")
    db.delete(r)
    db.commit()
    return {"message": "Reading deleted"}
