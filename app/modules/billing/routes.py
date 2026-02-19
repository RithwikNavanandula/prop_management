"""Billing routes – invoices, payments, late fees, payment methods."""
import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, func as sqlfunc
from typing import Optional
from datetime import date
from app.database import get_db
from app.auth.dependencies import get_current_user, require_permissions
from app.auth.models import UserAccount
from app.modules.billing.models import (
    Invoice, InvoiceLine, Payment, PaymentAllocation,
    LateFeeRule, PaymentMethod, ExchangeRateDaily, FxRateSnapshot, MultiCurrencyLedgerEntry
)
from app.modules.system.models import OrgSettings
from app.utils.event_service import emit_outbox_event

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/api/billing",
    tags=["Billing"],
    dependencies=[Depends(require_permissions(["billing", "payments", "finance", "accounting"]))],
)


def _parse_date(v):
    if v in (None, ""):
        return None
    if isinstance(v, date):
        return v
    if isinstance(v, str):
        try:
            return date.fromisoformat(v)
        except ValueError:
            raise HTTPException(400, "Invalid date format. Use YYYY-MM-DD")
    raise HTTPException(400, "Invalid date format. Use YYYY-MM-DD")


def _latest_rate(db: Session, on_date: date, from_currency: str, to_currency: str):
    q = db.query(ExchangeRateDaily).filter(
        ExchangeRateDaily.from_currency == from_currency,
        ExchangeRateDaily.to_currency == to_currency,
        ExchangeRateDaily.rate_date <= on_date,
    ).order_by(ExchangeRateDaily.rate_date.desc(), ExchangeRateDaily.id.desc())
    return q.first()


def _tenant_base_currency(db: Session, user: UserAccount) -> str:
    if not user.tenant_org_id:
        return "USD"
    s = db.query(OrgSettings).filter(OrgSettings.tenant_org_id == user.tenant_org_id).first()
    return (s.base_currency if s and s.base_currency else "USD")


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
    payload = {k: v for k, v in data.items() if hasattr(Invoice, k) and k != "lines"}
    if "invoice_date" in payload:
        payload["invoice_date"] = _parse_date(payload["invoice_date"])
    if "due_date" in payload:
        payload["due_date"] = _parse_date(payload["due_date"])
    if "posting_date" in payload:
        payload["posting_date"] = _parse_date(payload["posting_date"])

    inv = Invoice(**payload)
    inv.created_by = user.id
    if user.tenant_org_id:
        inv.tenant_org_id = user.tenant_org_id
    if not inv.base_currency:
        inv.base_currency = _tenant_base_currency(db, user)
    if not inv.document_currency:
        inv.document_currency = inv.base_currency or "USD"
    db.add(inv)
    db.commit()
    db.refresh(inv)
    for line in data.get("lines", []):
        il = InvoiceLine(**{k: v for k, v in line.items() if hasattr(InvoiceLine, k)})
        il.invoice_id = inv.id
        db.add(il)

    # Set FX/base values and write ledger entry.
    fx_rate = 1.0
    if (inv.document_currency or "USD") != (inv.base_currency or "USD"):
        rate_row = _latest_rate(db, inv.invoice_date, inv.document_currency, inv.base_currency)
        if rate_row:
            fx_rate = float(rate_row.rate or 1.0)
            inv.exchange_rate_id = rate_row.id
    inv.exchange_rate_value = fx_rate
    inv.base_amount = float(inv.document_amount or 0) * fx_rate
    inv.fx_difference_amount = float(inv.base_amount or 0) - float(inv.document_amount or 0)
    tenant_id_for_entries = user.tenant_org_id or inv.tenant_org_id
    if tenant_id_for_entries:
        db.add(MultiCurrencyLedgerEntry(
            tenant_org_id=tenant_id_for_entries,
            reference_type="Invoice",
            reference_id=inv.id,
            posting_date=inv.posting_date or inv.invoice_date,
            txn_currency=inv.document_currency or "USD",
            txn_amount=inv.document_amount or 0,
            base_currency=inv.base_currency or "USD",
            base_amount=inv.base_amount or 0,
            fx_rate=inv.exchange_rate_value or 1,
            entry_side="Debit",
            notes=f"Invoice {inv.invoice_number}",
            created_by=user.id,
        ))
    emit_outbox_event(
        db=db,
        tenant_org_id=user.tenant_org_id,
        event_type="invoice.created",
        aggregate_type="Invoice",
        aggregate_id=inv.id,
        payload={"invoice_number": inv.invoice_number, "tenant_id": inv.tenant_id, "total_amount": float(inv.total_amount or 0)},
        event_key=f"invoice.created.{inv.id}",
    )
    db.commit()
    db.refresh(inv)
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
    payload = {k: v for k, v in data.items() if hasattr(Payment, k) and k != "allocations"}
    if "payment_date" in payload:
        payload["payment_date"] = _parse_date(payload["payment_date"])
    pmt = Payment(**payload)
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
    tenant_id_for_entries = user.tenant_org_id or pmt.tenant_org_id
    if tenant_id_for_entries:
        db.add(MultiCurrencyLedgerEntry(
            tenant_org_id=tenant_id_for_entries,
            reference_type="Payment",
            reference_id=pmt.id,
            posting_date=pmt.payment_date,
            txn_currency=pmt.currency or "USD",
            txn_amount=pmt.amount or 0,
            base_currency=pmt.currency or "USD",
            base_amount=pmt.amount or 0,
            fx_rate=1,
            entry_side="Credit",
            notes=f"Payment {pmt.payment_number}",
            created_by=user.id,
        ))
    emit_outbox_event(
        db=db,
        tenant_org_id=user.tenant_org_id,
        event_type="payment.received",
        aggregate_type="Payment",
        aggregate_id=pmt.id,
        payload={"payment_number": pmt.payment_number, "tenant_id": pmt.tenant_id, "amount": float(pmt.amount or 0)},
        event_key=f"payment.received.{pmt.id}",
    )
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


@router.get("/fx-rates")
def list_fx_rates(
    from_currency: Optional[str] = None,
    to_currency: Optional[str] = None,
    rate_date: Optional[str] = None,
    db: Session = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    q = db.query(ExchangeRateDaily)
    if from_currency:
        q = q.filter(ExchangeRateDaily.from_currency == from_currency)
    if to_currency:
        q = q.filter(ExchangeRateDaily.to_currency == to_currency)
    if rate_date:
        q = q.filter(ExchangeRateDaily.rate_date == _parse_date(rate_date))
    items = q.order_by(ExchangeRateDaily.rate_date.desc(), ExchangeRateDaily.id.desc()).limit(500).all()
    return {"total": len(items), "items": [_to_dict(x) for x in items]}


@router.post("/fx-rates", status_code=201)
def create_fx_rate(data: dict, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    d = {k: v for k, v in data.items() if hasattr(ExchangeRateDaily, k)}
    if not d.get("rate_date"):
        raise HTTPException(400, "rate_date is required")
    d["rate_date"] = _parse_date(d["rate_date"])
    item = ExchangeRateDaily(**d)
    db.add(item)
    db.commit()
    db.refresh(item)
    return _to_dict(item)


@router.post("/fx-snapshots/generate", status_code=201)
def generate_fx_snapshot(data: dict, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    if not user.tenant_org_id:
        raise HTTPException(400, "User not associated with tenant org")
    snapshot_date = _parse_date(data.get("snapshot_date")) or date.today()
    q = db.query(ExchangeRateDaily).filter(ExchangeRateDaily.rate_date <= snapshot_date)
    rows = q.order_by(ExchangeRateDaily.rate_date.desc(), ExchangeRateDaily.id.desc()).all()
    latest_by_pair = {}
    for r in rows:
        key = (r.from_currency, r.to_currency)
        if key not in latest_by_pair:
            latest_by_pair[key] = r

    created = []
    for pair, r in latest_by_pair.items():
        s = FxRateSnapshot(
            tenant_org_id=user.tenant_org_id,
            snapshot_date=snapshot_date,
            from_currency=r.from_currency,
            to_currency=r.to_currency,
            rate=r.rate,
            source=r.source,
            exchange_rate_daily_id=r.id,
            created_by=user.id,
        )
        db.add(s)
        created.append(s)
    db.commit()
    return {"snapshot_date": str(snapshot_date), "created": len(created)}


@router.get("/fx-snapshots")
def list_fx_snapshots(
    snapshot_date: Optional[str] = None,
    from_currency: Optional[str] = None,
    to_currency: Optional[str] = None,
    db: Session = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    q = db.query(FxRateSnapshot)
    if user.tenant_org_id:
        q = q.filter(FxRateSnapshot.tenant_org_id == user.tenant_org_id)
    if snapshot_date:
        q = q.filter(FxRateSnapshot.snapshot_date == _parse_date(snapshot_date))
    if from_currency:
        q = q.filter(FxRateSnapshot.from_currency == from_currency)
    if to_currency:
        q = q.filter(FxRateSnapshot.to_currency == to_currency)
    items = q.order_by(FxRateSnapshot.snapshot_date.desc(), FxRateSnapshot.id.desc()).limit(1000).all()
    return {"total": len(items), "items": [_to_dict(x) for x in items]}


@router.post("/invoices/{inv_id}/revalue")
def revalue_invoice(inv_id: int, data: dict, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    q = db.query(Invoice).filter(Invoice.id == inv_id)
    if user.tenant_org_id:
        q = q.filter(Invoice.tenant_org_id == user.tenant_org_id)
    inv = q.first()
    if not inv:
        raise HTTPException(404, "Invoice not found")
    as_of = _parse_date(data.get("as_of")) or date.today()
    if (inv.document_currency or "USD") == (inv.base_currency or "USD"):
        return {"invoice_id": inv.id, "message": "No revaluation needed for same currency"}
    rate_row = _latest_rate(db, as_of, inv.document_currency, inv.base_currency)
    if not rate_row:
        raise HTTPException(400, "No FX rate found for currency pair")
    old_base = float(inv.base_amount or 0)
    new_base = float(inv.document_amount or 0) * float(rate_row.rate or 1)
    gain_loss = new_base - old_base
    inv.base_amount = new_base
    inv.exchange_rate_id = rate_row.id
    inv.exchange_rate_value = rate_row.rate
    inv.fx_difference_amount = gain_loss
    tenant_id_for_entries = user.tenant_org_id or inv.tenant_org_id
    if tenant_id_for_entries:
        db.add(MultiCurrencyLedgerEntry(
            tenant_org_id=tenant_id_for_entries,
            reference_type="Revaluation",
            reference_id=inv.id,
            posting_date=as_of,
            txn_currency=inv.document_currency or "USD",
            txn_amount=inv.document_amount or 0,
            base_currency=inv.base_currency or "USD",
            base_amount=new_base,
            fx_rate=rate_row.rate,
            entry_side="Debit" if gain_loss >= 0 else "Credit",
            notes=f"FX revaluation for invoice {inv.invoice_number}",
            created_by=user.id,
        ))
    emit_outbox_event(
        db=db,
        tenant_org_id=user.tenant_org_id,
        event_type="invoice.revalued",
        aggregate_type="Invoice",
        aggregate_id=inv.id,
        payload={"invoice_number": inv.invoice_number, "as_of": str(as_of), "gain_loss": gain_loss},
        event_key=f"invoice.revalued.{inv.id}.{as_of}",
    )
    db.commit()
    db.refresh(inv)
    return {"invoice": _to_dict(inv), "gain_loss": gain_loss}


@router.get("/ledger-entries")
def list_ledger_entries(
    reference_type: Optional[str] = None,
    reference_id: Optional[int] = None,
    db: Session = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    q = db.query(MultiCurrencyLedgerEntry)
    if user.tenant_org_id:
        q = q.filter(MultiCurrencyLedgerEntry.tenant_org_id == user.tenant_org_id)
    if reference_type:
        q = q.filter(MultiCurrencyLedgerEntry.reference_type == reference_type)
    if reference_id:
        q = q.filter(MultiCurrencyLedgerEntry.reference_id == reference_id)
    items = q.order_by(MultiCurrencyLedgerEntry.id.desc()).limit(500).all()
    return {"total": len(items), "items": [_to_dict(x) for x in items]}


def _to_dict(obj):
    return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}
