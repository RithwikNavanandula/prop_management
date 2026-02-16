"""Leasing CRUD routes."""
import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import Optional
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
from app.database import get_db
from app.auth.dependencies import get_current_user
from app.auth.models import UserAccount
from app.modules.leasing.models import Lease, RentSchedule, SecurityDeposit, LeaseUnitLink
from app.modules.properties.models import Unit

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/leases", tags=["Leasing"])


@router.get("")
def list_leases(search: Optional[str] = None, status: Optional[str] = None,
                property_id: Optional[int] = None, unit_id: Optional[int] = None,
                skip: int = 0, limit: int = 50,
                db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    q = db.query(Lease).filter(Lease.is_deleted == False)
    # Multi-tenant isolation
    if user.tenant_org_id:
        q = q.filter(Lease.tenant_org_id == user.tenant_org_id)
    if status:
        q = q.filter(Lease.lease_status == status)
    if property_id:
        q = q.filter(Lease.property_id == property_id)
    if unit_id:
        q = q.filter(Lease.unit_id == unit_id)
    if search:
        q = q.filter(or_(Lease.lease_number.ilike(f"%{search}%")))
    total = q.count()
    items = q.order_by(Lease.id.desc()).offset(skip).limit(limit).all()
    return {"total": total, "items": [_to_dict(l) for l in items]}


@router.post("", status_code=201)
def create_lease(data: dict, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    # 1. Validate required fields
    required = ["lease_number", "property_id", "tenant_id", "start_date", "end_date", "base_rent_amount"]
    for field in required:
        val = data.get(field)
        if val in (None, "", "NaN", "null"):
            raise HTTPException(400, f"Field '{field}' is required and cannot be null/empty")

    # 2. Build lease_data with type coercion
    lease_data = {}
    for k, v in data.items():
        if hasattr(Lease, k) and v not in ("", None, "NaN", "null"):
            if k in ("property_id", "unit_id", "tenant_id", "owner_id", "notice_period_days"):
                try:
                    lease_data[k] = int(v) if not isinstance(v, int) else v
                except (ValueError, TypeError) as e:
                    logger.warning("Failed to convert %s=%r to int: %s", k, v, e)
            elif k in ("base_rent_amount", "discounts", "service_charge_percent", "revenue_share_percent"):
                try:
                    lease_data[k] = float(v) if not isinstance(v, float) else v
                except (ValueError, TypeError) as e:
                    logger.warning("Failed to convert %s=%r to float: %s", k, v, e)
            elif k in ("start_date", "end_date", "possession_date", "termination_date"):
                try:
                    lease_data[k] = date.fromisoformat(v) if isinstance(v, str) else v
                except (ValueError, TypeError) as e:
                    logger.warning("Failed to parse date %s=%r: %s", k, v, e)
            else:
                lease_data[k] = v

    try:
        lease = Lease(**lease_data)
        lease.created_by = user.id
        if user.tenant_org_id:
            lease.tenant_org_id = user.tenant_org_id

        db.add(lease)
        # Flush to get lease.id BEFORE creating the link
        db.flush()

        # Update unit status and create link record
        if lease.unit_id:
            unit = db.query(Unit).filter(Unit.id == lease.unit_id).first()
            if unit:
                unit.current_status = "Occupied"
            # Now lease.id is available — no NULL FK
            link = LeaseUnitLink(
                lease_id=lease.id,
                unit_id=lease.unit_id,
                allocated_rent=lease.base_rent_amount
            )
            db.add(link)

        db.commit()
        db.refresh(lease)

        # 3. Generate Rent Schedule
        try:
            generate_rent_schedule(db, lease)
        except Exception as e:
            logger.error("Error generating rent schedule for lease %s: %s", lease.id, e, exc_info=True)

        return _to_dict(lease)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error creating lease: %s", e, exc_info=True)
        db.rollback()
        raise HTTPException(500, detail=str(e))


@router.get("/{lease_id}")
def get_lease(lease_id: int, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    lease = db.query(Lease).filter(Lease.id == lease_id).first()
    if not lease:
        raise HTTPException(404, "Lease not found")
    d = _to_dict(lease)
    d["rent_schedules"] = [_to_dict(rs) for rs in db.query(RentSchedule).filter(RentSchedule.lease_id == lease_id).all()]
    d["deposits"] = [_to_dict(sd) for sd in db.query(SecurityDeposit).filter(SecurityDeposit.lease_id == lease_id).all()]
    return d


@router.put("/{lease_id}")
def update_lease(lease_id: int, data: dict, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    lease = db.query(Lease).filter(Lease.id == lease_id).first()
    if not lease:
        raise HTTPException(404, "Lease not found")
    for k, v in data.items():
        if hasattr(lease, k) and k not in ("id", "created_at"):
            setattr(lease, k, v)
    lease.updated_by = user.id
    db.commit()
    db.refresh(lease)
    return _to_dict(lease)


@router.post("/{lease_id}/activate")
def activate_lease(lease_id: int, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    lease = db.query(Lease).filter(Lease.id == lease_id).first()
    if not lease:
        raise HTTPException(404, "Lease not found")
    lease.lease_status = "Active"
    lease.updated_by = user.id
    db.commit()
    return {"message": "Lease activated", "lease_id": lease_id}


@router.post("/{lease_id}/terminate")
def terminate_lease(lease_id: int, data: dict, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    lease = db.query(Lease).filter(Lease.id == lease_id).first()
    if not lease:
        raise HTTPException(404, "Lease not found")
    lease.lease_status = "Terminated"
    lease.termination_date = data.get("termination_date", date.today().isoformat())
    lease.termination_reason = data.get("reason", "")
    if lease.unit_id:
        unit = db.query(Unit).filter(Unit.id == lease.unit_id).first()
        if unit:
            unit.current_status = "Vacant"
    db.commit()
    return {"message": "Lease terminated"}


@router.get("/{lease_id}/rent-schedule")
def get_rent_schedule(lease_id: int, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    items = db.query(RentSchedule).filter(RentSchedule.lease_id == lease_id).order_by(RentSchedule.due_date).all()
    return {"items": [_to_dict(rs) for rs in items]}


def generate_rent_schedule(db: Session, lease: Lease):
    """Calculates and inserts rent schedule entries for the lease duration.

    Uses dateutil.relativedelta for correct month/quarter/year increments.
    """
    start = lease.start_date
    end = lease.end_date
    amount = lease.base_rent_amount
    freq = lease.rent_frequency or "Monthly"

    current = start
    while current < end:
        # Determine next period start using relativedelta
        if freq == "Monthly":
            next_date = current + relativedelta(months=1)
        elif freq == "Quarterly":
            next_date = current + relativedelta(months=3)
        elif freq == "Yearly":
            next_date = current + relativedelta(years=1)
        else:
            break  # Unsupported frequency

        period_end = next_date - timedelta(days=1)
        if period_end > end:
            period_end = end

        rs = RentSchedule(
            tenant_org_id=lease.tenant_org_id,
            lease_id=lease.id,
            due_date=current,
            period_start=current,
            period_end=period_end,
            scheduled_amount=amount,
            total_amount=amount,
            outstanding_amount=amount,
            currency=lease.base_rent_currency or "USD"
        )
        db.add(rs)
        current = next_date

    db.commit()


def _to_dict(obj):
    return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}
