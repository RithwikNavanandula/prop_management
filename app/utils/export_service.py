"""Export utilities – CSV + Excel."""
import io
import csv
import logging
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import Optional
from datetime import date
from app.database import get_db
from app.auth.dependencies import get_current_user
from app.auth.models import UserAccount
from app.modules.properties.models import Property, Unit
from app.modules.leasing.models import Lease
from app.modules.billing.models import Invoice, Payment

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/export", tags=["Export"])


def _rows_to_csv(rows: list[dict]) -> io.StringIO:
    if not rows:
        buf = io.StringIO()
        buf.write("No data\n")
        buf.seek(0)
        return buf
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=rows[0].keys())
    w.writeheader()
    w.writerows(rows)
    buf.seek(0)
    return buf


def _to_dict(obj):
    d = {}
    for c in obj.__table__.columns:
        val = getattr(obj, c.name)
        d[c.name] = str(val) if val is not None else ""
    return d


@router.get("/properties")
def export_properties(db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    q = db.query(Property).filter(Property.is_deleted == False)
    if user.tenant_org_id:
        q = q.filter(Property.tenant_org_id == user.tenant_org_id)
    rows = [_to_dict(p) for p in q.all()]
    buf = _rows_to_csv(rows)
    return StreamingResponse(buf, media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=properties.csv"})


@router.get("/units")
def export_units(property_id: Optional[int] = None, db: Session = Depends(get_db),
                 user: UserAccount = Depends(get_current_user)):
    q = db.query(Unit).filter(Unit.is_deleted == False)
    if user.tenant_org_id:
        q = q.filter(Unit.tenant_org_id == user.tenant_org_id)
    if property_id:
        q = q.filter(Unit.property_id == property_id)
    rows = [_to_dict(u) for u in q.all()]
    buf = _rows_to_csv(rows)
    return StreamingResponse(buf, media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=units.csv"})


@router.get("/leases")
def export_leases(db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    q = db.query(Lease)
    if user.tenant_org_id:
        q = q.filter(Lease.tenant_org_id == user.tenant_org_id)
    rows = [_to_dict(l) for l in q.all()]
    buf = _rows_to_csv(rows)
    return StreamingResponse(buf, media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=leases.csv"})


@router.get("/invoices")
def export_invoices(status: Optional[str] = None, db: Session = Depends(get_db),
                    user: UserAccount = Depends(get_current_user)):
    q = db.query(Invoice)
    if user.tenant_org_id:
        q = q.filter(Invoice.tenant_org_id == user.tenant_org_id)
    if status:
        q = q.filter(Invoice.invoice_status == status)
    rows = [_to_dict(i) for i in q.all()]
    buf = _rows_to_csv(rows)
    return StreamingResponse(buf, media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=invoices.csv"})


@router.get("/payments")
def export_payments(db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    q = db.query(Payment)
    if user.tenant_org_id:
        q = q.filter(Payment.tenant_org_id == user.tenant_org_id)
    rows = [_to_dict(p) for p in q.all()]
    buf = _rows_to_csv(rows)
    return StreamingResponse(buf, media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=payments.csv"})
