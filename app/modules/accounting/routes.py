"""Accounting API routes – full CRUD + reports."""
import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
from app.database import get_db
from app.auth.dependencies import get_current_user
from app.auth.models import UserAccount
from app.modules.accounting.models import (
    ChartOfAccount, JournalEntry, JournalEntryLine,
    GLAccountBalance, BankAccount, VendorBill, OwnerDistribution
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/accounting", tags=["Accounting"])


def _tenant_q(q, model, user):
    if user.tenant_org_id and hasattr(model, "tenant_org_id"):
        return q.filter(model.tenant_org_id == user.tenant_org_id)
    return q


# ─── Chart of Accounts ───
@router.get("/chart-of-accounts")
def list_accounts(type: Optional[str] = None, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    q = db.query(ChartOfAccount).filter(ChartOfAccount.status == "Active")
    q = _tenant_q(q, ChartOfAccount, user)
    if type:
        q = q.filter(ChartOfAccount.account_type == type)
    items = q.order_by(ChartOfAccount.account_code).all()
    return {"total": len(items), "items": [_dict(a) for a in items]}


@router.post("/chart-of-accounts", status_code=201)
def create_account(data: dict, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    acc = ChartOfAccount(**{k: v for k, v in data.items() if hasattr(ChartOfAccount, k)})
    if user.tenant_org_id:
        acc.tenant_org_id = user.tenant_org_id
    db.add(acc)
    db.commit()
    db.refresh(acc)
    return _dict(acc)


@router.put("/chart-of-accounts/{acc_id}")
def update_account(acc_id: int, data: dict, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    acc = db.query(ChartOfAccount).filter(ChartOfAccount.id == acc_id).first()
    if not acc:
        raise HTTPException(404, "Account not found")
    for k, v in data.items():
        if hasattr(acc, k) and k not in ("id",):
            setattr(acc, k, v)
    db.commit()
    db.refresh(acc)
    return _dict(acc)


@router.delete("/chart-of-accounts/{acc_id}")
def delete_account(acc_id: int, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    acc = db.query(ChartOfAccount).filter(ChartOfAccount.id == acc_id).first()
    if not acc:
        raise HTTPException(404, "Account not found")
    acc.status = "Inactive"
    db.commit()
    return {"message": "Account deactivated"}


# ─── Journal Entries ───
@router.get("/journal-entries")
def list_journal_entries(start_date: Optional[date] = None, end_date: Optional[date] = None,
                         skip: int = 0, limit: int = 50,
                         db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    q = db.query(JournalEntry)
    q = _tenant_q(q, JournalEntry, user)
    if start_date:
        q = q.filter(JournalEntry.entry_date >= start_date)
    if end_date:
        q = q.filter(JournalEntry.entry_date <= end_date)
    total = q.count()
    items = q.order_by(JournalEntry.entry_date.desc()).offset(skip).limit(limit).all()
    res = []
    for je in items:
        je_dict = _dict(je)
        lines = db.query(JournalEntryLine).filter(JournalEntryLine.journal_entry_id == je.id).all()
        je_dict["lines"] = [_dict(l) for l in lines]
        res.append(je_dict)
    return {"total": total, "items": res}


@router.post("/journal-entries", status_code=201)
def create_journal_entry(data: dict, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    lines_data = data.pop("lines", [])
    je = JournalEntry(**{k: v for k, v in data.items() if hasattr(JournalEntry, k)})
    if user.tenant_org_id:
        je.tenant_org_id = user.tenant_org_id
    je.created_by = user.id
    db.add(je)
    db.flush()
    total_dr, total_cr = 0, 0
    for l_data in lines_data:
        line = JournalEntryLine(**{k: v for k, v in l_data.items() if hasattr(JournalEntryLine, k)})
        line.journal_entry_id = je.id
        total_dr += float(line.debit_amount or 0)
        total_cr += float(line.credit_amount or 0)
        db.add(line)
    je.total_debit = total_dr
    je.total_credit = total_cr
    if abs(total_dr - total_cr) > 0.01:
        db.rollback()
        raise HTTPException(400, "Journal Entry is not balanced")
    db.commit()
    db.refresh(je)
    return _dict(je)


# ─── Vendor Bills ───
@router.get("/vendor-bills")
def list_vendor_bills(status: Optional[str] = None, skip: int = 0, limit: int = 50,
                      db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    q = _tenant_q(db.query(VendorBill), VendorBill, user)
    if status:
        q = q.filter(VendorBill.status == status)
    total = q.count()
    items = q.order_by(VendorBill.id.desc()).offset(skip).limit(limit).all()
    return {"total": total, "items": [_dict(b) for b in items]}


@router.post("/vendor-bills", status_code=201)
def create_vendor_bill(data: dict, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    bill = VendorBill(**{k: v for k, v in data.items() if hasattr(VendorBill, k)})
    if user.tenant_org_id:
        bill.tenant_org_id = user.tenant_org_id
    bill.created_by = user.id
    db.add(bill)
    db.commit()
    db.refresh(bill)
    return _dict(bill)


@router.put("/vendor-bills/{bill_id}")
def update_vendor_bill(bill_id: int, data: dict, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    bill = db.query(VendorBill).filter(VendorBill.id == bill_id).first()
    if not bill:
        raise HTTPException(404, "Vendor bill not found")
    for k, v in data.items():
        if hasattr(bill, k) and k not in ("id",):
            setattr(bill, k, v)
    db.commit()
    db.refresh(bill)
    return _dict(bill)


# ─── Owner Distributions ───
@router.get("/distributions")
def list_distributions(owner_id: Optional[int] = None, skip: int = 0, limit: int = 50,
                       db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    q = _tenant_q(db.query(OwnerDistribution), OwnerDistribution, user)
    if owner_id:
        q = q.filter(OwnerDistribution.owner_id == owner_id)
    total = q.count()
    items = q.order_by(OwnerDistribution.id.desc()).offset(skip).limit(limit).all()
    return {"total": total, "items": [_dict(d) for d in items]}


@router.post("/distributions", status_code=201)
def create_distribution(data: dict, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    dist = OwnerDistribution(**{k: v for k, v in data.items() if hasattr(OwnerDistribution, k)})
    # Auto-calc net distribution
    gross = float(dist.gross_revenue or 0)
    expenses = float(dist.expenses or 0)
    mgmt_fee = float(dist.management_fee or 0)
    dist.net_distribution = gross - expenses - mgmt_fee
    if user.tenant_org_id:
        dist.tenant_org_id = user.tenant_org_id
    db.add(dist)
    db.commit()
    db.refresh(dist)
    return _dict(dist)


# ─── Bank Accounts ───
@router.get("/bank-accounts")
def list_bank_accounts(db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    q = _tenant_q(db.query(BankAccount), BankAccount, user)
    items = q.all()
    return {"total": len(items), "items": [_dict(b) for b in items]}


@router.post("/bank-accounts", status_code=201)
def create_bank_account(data: dict, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    ba = BankAccount(**{k: v for k, v in data.items() if hasattr(BankAccount, k)})
    if user.tenant_org_id:
        ba.tenant_org_id = user.tenant_org_id
    db.add(ba)
    db.commit()
    db.refresh(ba)
    return _dict(ba)


# ─── Reports ───
@router.get("/reports/balance-sheet")
def get_balance_sheet(as_of: date = Query(...), db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    accounts = db.query(ChartOfAccount).filter(ChartOfAccount.account_type.in_(["Asset", "Liability", "Equity"]))
    accounts = _tenant_q(accounts, ChartOfAccount, user).all()
    report = []
    for acc in accounts:
        balance = db.query(
            func.coalesce(func.sum(JournalEntryLine.debit_amount), 0) - func.coalesce(func.sum(JournalEntryLine.credit_amount), 0)
        ).join(JournalEntry, JournalEntryLine.journal_entry_id == JournalEntry.id
        ).filter(JournalEntryLine.account_id == acc.id, JournalEntry.entry_date <= as_of).scalar() or 0
        if acc.account_type in ["Liability", "Equity"]:
            balance = -balance
        report.append({"account_code": acc.account_code, "account_name": acc.account_name, "type": acc.account_type, "balance": float(balance)})
    return {"as_of": as_of, "data": report}


@router.get("/reports/income-statement")
def get_income_statement(start_date: date = Query(...), end_date: date = Query(...),
                         db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    accounts = db.query(ChartOfAccount).filter(ChartOfAccount.account_type.in_(["Revenue", "Expense"]))
    accounts = _tenant_q(accounts, ChartOfAccount, user).all()
    report = []
    for acc in accounts:
        balance = db.query(
            func.coalesce(func.sum(JournalEntryLine.credit_amount), 0) - func.coalesce(func.sum(JournalEntryLine.debit_amount), 0)
        ).join(JournalEntry, JournalEntryLine.journal_entry_id == JournalEntry.id
        ).filter(JournalEntryLine.account_id == acc.id,
                 JournalEntry.entry_date >= start_date, JournalEntry.entry_date <= end_date
        ).scalar() or 0
        if acc.account_type == "Expense":
            balance = -balance
        report.append({"account_code": acc.account_code, "account_name": acc.account_name, "type": acc.account_type, "balance": float(balance)})
    total_revenue = sum(r["balance"] for r in report if r["type"] == "Revenue")
    total_expenses = sum(r["balance"] for r in report if r["type"] == "Expense")
    return {"start_date": start_date, "end_date": end_date, "data": report,
            "total_revenue": total_revenue, "total_expenses": total_expenses,
            "net_income": total_revenue - total_expenses}


@router.get("/reports/trial-balance")
def get_trial_balance(as_of: date = Query(...), db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    accounts = _tenant_q(db.query(ChartOfAccount), ChartOfAccount, user).all()
    report = []
    total_dr, total_cr = 0, 0
    for acc in accounts:
        dr = db.query(func.coalesce(func.sum(JournalEntryLine.debit_amount), 0)
        ).join(JournalEntry, JournalEntryLine.journal_entry_id == JournalEntry.id
        ).filter(JournalEntryLine.account_id == acc.id, JournalEntry.entry_date <= as_of).scalar() or 0
        cr = db.query(func.coalesce(func.sum(JournalEntryLine.credit_amount), 0)
        ).join(JournalEntry, JournalEntryLine.journal_entry_id == JournalEntry.id
        ).filter(JournalEntryLine.account_id == acc.id, JournalEntry.entry_date <= as_of).scalar() or 0
        total_dr += float(dr)
        total_cr += float(cr)
        report.append({"account_code": acc.account_code, "account_name": acc.account_name,
                        "debit": float(dr), "credit": float(cr)})
    return {"as_of": as_of, "data": report, "total_debit": total_dr, "total_credit": total_cr}


def _dict(obj):
    return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}
