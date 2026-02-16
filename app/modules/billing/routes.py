"""Billing routes – invoices, payments, late fees, payment methods."""
import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, func as sqlfunc
from typing import Optional
from app.database import get_db
from app.auth.dependencies import get_current_user, require_permissions
from app.auth.models import UserAccount
from app.modules.billing.models import (
    Invoice, InvoiceLine, Payment, PaymentAllocation,
    LateFeeRule, PaymentMethod
)

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/api/billing",
    tags=["Billing"],
    dependencies=[Depends(require_permissions(["billing", "payments", "finance", "accounting"]))],
)


# ─── Invoices ───
@router.get("/invoices")
def list_invoices(status: Optional[str] = None, tenant_id: Optional[int] = None,
                  skip: int = 0, limit: int = 50,
                  db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    q = db.query(Invoice)
    if user.tenant_org_id:
        q = q.filter(Invoice.tenant_org_id == user.tenant_org_id)
    if status:
        q = q.filter(Invoice.invoice_status == status)
    if tenant_id:
        q = q.filter(Invoice.tenant_id == tenant_id)
    total = q.count()
    items = q.order_by(Invoice.id.desc()).offset(skip).limit(limit).all()
    return {"total": total, "items": [_to_dict(i) for i in items]}


@router.post("/invoices", status_code=201)
def create_invoice(data: dict, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    inv = Invoice(**{k: v for k, v in data.items() if hasattr(Invoice, k) and k != "lines"})
    inv.created_by = user.id
    if user.tenant_org_id:
        inv.tenant_org_id = user.tenant_org_id
    db.add(inv)
    db.commit()
    db.refresh(inv)
    for line in data.get("lines", []):
        il = InvoiceLine(**{k: v for k, v in line.items() if hasattr(InvoiceLine, k)})
        il.invoice_id = inv.id
        db.add(il)
    db.commit()
    return _to_dict(inv)


@router.get("/invoices/{inv_id}")
def get_invoice(inv_id: int, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    inv = db.query(Invoice).filter(Invoice.id == inv_id).first()
    if not inv:
        raise HTTPException(404, "Invoice not found")
    d = _to_dict(inv)
    d["lines"] = [_to_dict(l) for l in db.query(InvoiceLine).filter(InvoiceLine.invoice_id == inv_id).all()]
    return d


@router.put("/invoices/{inv_id}")
def update_invoice(inv_id: int, data: dict, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    inv = db.query(Invoice).filter(Invoice.id == inv_id).first()
    if not inv:
        raise HTTPException(404, "Invoice not found")
    for k, v in data.items():
        if hasattr(inv, k) and k not in ("id", "created_at"):
            setattr(inv, k, v)
    db.commit()
    db.refresh(inv)
    return _to_dict(inv)


@router.post("/invoices/{inv_id}/post")
def post_invoice(inv_id: int, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    inv = db.query(Invoice).filter(Invoice.id == inv_id).first()
    if not inv:
        raise HTTPException(404, "Invoice not found")
    if inv.invoice_status != "Draft":
        raise HTTPException(400, "Only Draft invoices can be posted")
    inv.invoice_status = "Posted"
    db.commit()
    return {"message": "Invoice posted", "invoice_id": inv_id}


@router.post("/invoices/{inv_id}/void")
def void_invoice(inv_id: int, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    inv = db.query(Invoice).filter(Invoice.id == inv_id).first()
    if not inv:
        raise HTTPException(404, "Invoice not found")
    inv.invoice_status = "Voided"
    db.commit()
    return {"message": "Invoice voided", "invoice_id": inv_id}


# ─── Payments ───
@router.get("/payments")
def list_payments(tenant_id: Optional[int] = None, skip: int = 0, limit: int = 50,
                  db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    q = db.query(Payment)
    if user.tenant_org_id:
        q = q.filter(Payment.tenant_org_id == user.tenant_org_id)
    if tenant_id:
        q = q.filter(Payment.tenant_id == tenant_id)
    total = q.count()
    items = q.order_by(Payment.id.desc()).offset(skip).limit(limit).all()
    return {"total": total, "items": [_to_dict(p) for p in items]}


@router.post("/payments", status_code=201)
def create_payment(data: dict, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    pmt = Payment(**{k: v for k, v in data.items() if hasattr(Payment, k) and k != "allocations"})
    pmt.created_by = user.id
    if user.tenant_org_id:
        pmt.tenant_org_id = user.tenant_org_id
    db.add(pmt)
    db.commit()
    db.refresh(pmt)
    for alloc in data.get("allocations", []):
        pa = PaymentAllocation(payment_id=pmt.id, invoice_id=alloc["invoice_id"],
                               allocated_amount=alloc["amount"], currency=pmt.currency)
        db.add(pa)
        inv = db.query(Invoice).filter(Invoice.id == alloc["invoice_id"]).first()
        if inv:
            db.flush()
            total_allocated = db.query(
                sqlfunc.coalesce(sqlfunc.sum(PaymentAllocation.allocated_amount), 0)
            ).filter(PaymentAllocation.invoice_id == inv.id).scalar()
            if float(total_allocated) >= float(inv.total_amount or 0):
                inv.invoice_status = "Paid"
            else:
                inv.invoice_status = "PartiallyPaid"
    db.commit()
    return _to_dict(pmt)


@router.get("/payments/{pmt_id}")
def get_payment(pmt_id: int, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    pmt = db.query(Payment).filter(Payment.id == pmt_id).first()
    if not pmt:
        raise HTTPException(404, "Payment not found")
    d = _to_dict(pmt)
    d["allocations"] = [_to_dict(a) for a in db.query(PaymentAllocation).filter(PaymentAllocation.payment_id == pmt_id).all()]
    return d


@router.post("/payments/{pmt_id}/void")
def void_payment(pmt_id: int, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    pmt = db.query(Payment).filter(Payment.id == pmt_id).first()
    if not pmt:
        raise HTTPException(404, "Payment not found")
    pmt.status = "Voided"
    # Revert allocated invoices
    allocs = db.query(PaymentAllocation).filter(PaymentAllocation.payment_id == pmt_id).all()
    for alloc in allocs:
        inv = db.query(Invoice).filter(Invoice.id == alloc.invoice_id).first()
        if inv and inv.invoice_status == "Paid":
            inv.invoice_status = "Posted"
    db.commit()
    return {"message": "Payment voided"}


# ─── Late Fee Rules ───
@router.get("/late-fee-rules")
def list_late_fee_rules(db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    items = db.query(LateFeeRule).all()
    return {"total": len(items), "items": [_to_dict(r) for r in items]}


@router.post("/late-fee-rules", status_code=201)
def create_late_fee_rule(data: dict, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    rule = LateFeeRule(**{k: v for k, v in data.items() if hasattr(LateFeeRule, k)})
    if user.tenant_org_id:
        rule.tenant_org_id = user.tenant_org_id
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return _to_dict(rule)


@router.put("/late-fee-rules/{rule_id}")
def update_late_fee_rule(rule_id: int, data: dict, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    rule = db.query(LateFeeRule).filter(LateFeeRule.id == rule_id).first()
    if not rule:
        raise HTTPException(404, "Rule not found")
    for k, v in data.items():
        if hasattr(rule, k) and k not in ("id",):
            setattr(rule, k, v)
    db.commit()
    db.refresh(rule)
    return _to_dict(rule)


@router.delete("/late-fee-rules/{rule_id}")
def delete_late_fee_rule(rule_id: int, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    rule = db.query(LateFeeRule).filter(LateFeeRule.id == rule_id).first()
    if not rule:
        raise HTTPException(404, "Rule not found")
    db.delete(rule)
    db.commit()
    return {"message": "Rule deleted"}


# ─── Payment Methods ───
@router.get("/payment-methods")
def list_payment_methods(db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    items = db.query(PaymentMethod).all()
    return {"total": len(items), "items": [_to_dict(m) for m in items]}


@router.post("/payment-methods", status_code=201)
def create_payment_method(data: dict, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    method = PaymentMethod(**{k: v for k, v in data.items() if hasattr(PaymentMethod, k)})
    db.add(method)
    db.commit()
    db.refresh(method)
    return _to_dict(method)


@router.put("/payment-methods/{method_id}")
def update_payment_method(method_id: int, data: dict, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    method = db.query(PaymentMethod).filter(PaymentMethod.id == method_id).first()
    if not method:
        raise HTTPException(404, "Payment method not found")
    for k, v in data.items():
        if hasattr(method, k) and k not in ("id",):
            setattr(method, k, v)
    db.commit()
    db.refresh(method)
    return _to_dict(method)


def _to_dict(obj):
    return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}
