"""Lease renewal and auto-billing API endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from datetime import date
from app.database import get_db
from app.auth.dependencies import get_current_user
from app.auth.models import UserAccount
from app.utils.lease_service import detect_expiring_leases, renew_lease, auto_terminate_expired
from app.utils.billing_service import generate_invoices_for_today, apply_late_fees

router = APIRouter(prefix="/api/automation", tags=["Automation"])


@router.get("/expiring-leases")
def api_expiring_leases(days: int = 60, user: UserAccount = Depends(get_current_user)):
    return {"leases": detect_expiring_leases(days)}


@router.post("/renew-lease/{lease_id}")
def api_renew_lease(lease_id: int, data: dict = {}, user: UserAccount = Depends(get_current_user)):
    result = renew_lease(
        lease_id,
        new_end_date=data.get("new_end_date"),
        new_rent=data.get("new_rent"),
        escalation_pct=data.get("escalation_pct")
    )
    if result.get("error"):
        raise HTTPException(400, result["error"])
    return result


@router.post("/auto-terminate")
def api_auto_terminate(user: UserAccount = Depends(get_current_user)):
    count = auto_terminate_expired()
    return {"terminated": count}


@router.post("/generate-invoices")
def api_generate_invoices(user: UserAccount = Depends(get_current_user)):
    count = generate_invoices_for_today()
    return {"invoices_created": count}


@router.post("/apply-late-fees")
def api_apply_late_fees(user: UserAccount = Depends(get_current_user)):
    count = apply_late_fees()
    return {"fees_applied": count}
