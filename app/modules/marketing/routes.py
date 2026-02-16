"""Marketing API routes – listings, leads, applications, screening."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime
from app.database import get_db
from app.auth.dependencies import get_current_user, require_permissions
from app.auth.models import UserAccount
from app.modules.marketing.models import (
    Listing, Lead, Application, ScreeningResult
)

router = APIRouter(
    prefix="/api/marketing",
    tags=["Marketing"],
    dependencies=[Depends(require_permissions(["marketing", "sales", "crm"]))],
)


# --- Listings ---
@router.get("/listings")
def list_listings(status: Optional[str] = None, is_published: Optional[bool] = None,
                  db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    q = db.query(Listing)
    if status:
        q = q.filter(Listing.status == status)
    if is_published is not None:
        q = q.filter(Listing.is_published == is_published)
    if user.tenant_org_id:
        q = q.filter(Listing.tenant_org_id == user.tenant_org_id)
    items = q.all()
    return {"total": len(items), "items": [_dict(x) for x in items]}


@router.post("/listings", status_code=201)
def create_listing(data: dict, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    l = Listing(**{k: v for k, v in data.items() if hasattr(Listing, k)})
    if user.tenant_org_id:
        l.tenant_org_id = user.tenant_org_id
    db.add(l)
    db.commit()
    db.refresh(l)
    return _dict(l)


@router.put("/listings/{listing_id}")
def update_listing(listing_id: int, data: dict, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    l = db.query(Listing).filter(Listing.id == listing_id).first()
    if not l:
        raise HTTPException(404, "Listing not found")
    for k, v in data.items():
        if hasattr(l, k) and k not in ("id",):
            setattr(l, k, v)
    db.commit()
    db.refresh(l)
    return _dict(l)


# --- Leads ---
@router.get("/leads")
def list_leads(status: Optional[str] = None, db: Session = Depends(get_db),
               user: UserAccount = Depends(get_current_user)):
    q = db.query(Lead)
    if status:
        q = q.filter(Lead.lead_status == status)
    if user.tenant_org_id:
        q = q.filter(Lead.tenant_org_id == user.tenant_org_id)
    items = q.all()
    return {"total": len(items), "items": [_dict(x) for x in items]}


@router.post("/leads", status_code=201)
def create_lead(data: dict, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    l = Lead(**{k: v for k, v in data.items() if hasattr(Lead, k)})
    if user.tenant_org_id:
        l.tenant_org_id = user.tenant_org_id
    l.first_contact_date = datetime.utcnow()
    db.add(l)
    db.commit()
    db.refresh(l)
    return _dict(l)


@router.put("/leads/{lead_id}")
def update_lead(lead_id: int, data: dict, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    l = db.query(Lead).filter(Lead.id == lead_id).first()
    if not l:
        raise HTTPException(404, "Lead not found")
    for k, v in data.items():
        if hasattr(l, k) and k not in ("id",):
            setattr(l, k, v)
    l.last_contact_date = datetime.utcnow()
    db.commit()
    db.refresh(l)
    return _dict(l)


# --- Applications ---
@router.get("/applications")
def list_applications(status: Optional[str] = None, db: Session = Depends(get_db),
                      user: UserAccount = Depends(get_current_user)):
    q = db.query(Application)
    if status:
        q = q.filter(Application.status == status)
    if user.tenant_org_id:
        q = q.filter(Application.tenant_org_id == user.tenant_org_id)
    items = q.all()
    return {"total": len(items), "items": [_dict(x) for x in items]}


@router.post("/applications", status_code=201)
def create_application(data: dict, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    app_obj = Application(**{k: v for k, v in data.items() if hasattr(Application, k)})
    if user.tenant_org_id:
        app_obj.tenant_org_id = user.tenant_org_id
    db.add(app_obj)
    db.commit()
    db.refresh(app_obj)
    return _dict(app_obj)


@router.put("/applications/{app_id}")
def update_application(app_id: int, data: dict, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    app_obj = db.query(Application).filter(Application.id == app_id).first()
    if not app_obj:
        raise HTTPException(404, "Application not found")
    for k, v in data.items():
        if hasattr(app_obj, k) and k not in ("id",):
            setattr(app_obj, k, v)
    db.commit()
    db.refresh(app_obj)
    return _dict(app_obj)


# --- Screening ---
@router.post("/applications/{app_id}/screening", status_code=201)
def create_screening(app_id: int, data: dict, db: Session = Depends(get_db),
                     user: UserAccount = Depends(get_current_user)):
    sr = ScreeningResult(**{k: v for k, v in data.items() if hasattr(ScreeningResult, k)})
    sr.application_id = app_id
    db.add(sr)
    db.commit()
    db.refresh(sr)
    return _dict(sr)


@router.get("/applications/{app_id}/screening")
def list_screening(app_id: int, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    items = db.query(ScreeningResult).filter(ScreeningResult.application_id == app_id).all()
    return {"total": len(items), "items": [_dict(s) for s in items]}


def _dict(obj):
    return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}
