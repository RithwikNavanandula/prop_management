"""Compliance API routes – requirements, documents, inspections, compliance items."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional
from datetime import date
from app.database import get_db
from app.auth.dependencies import get_current_user, require_permissions
from app.auth.models import UserAccount
from app.modules.compliance.models import (
    ComplianceRequirement, Document, DocumentType, Inspection, ComplianceItem
)

router = APIRouter(
    prefix="/api/compliance",
    tags=["Compliance"],
    dependencies=[Depends(require_permissions(["compliance", "portfolio"]))],
)


# --- Requirements ---
@router.get("/requirements")
def list_requirements(entity_type: Optional[str] = None, db: Session = Depends(get_db),
                      user: UserAccount = Depends(get_current_user)):
    q = db.query(ComplianceRequirement).filter(ComplianceRequirement.is_active == True)
    if entity_type:
        q = q.filter(ComplianceRequirement.entity_type == entity_type)
    if user.tenant_org_id:
        q = q.filter(ComplianceRequirement.tenant_org_id == user.tenant_org_id)
    items = q.all()
    return {"total": len(items), "items": [_dict(x) for x in items]}


@router.post("/requirements", status_code=201)
def create_requirement(data: dict, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    r = ComplianceRequirement(**{k: v for k, v in data.items() if hasattr(ComplianceRequirement, k)})
    if user.tenant_org_id:
        r.tenant_org_id = user.tenant_org_id
    db.add(r)
    db.commit()
    db.refresh(r)
    return _dict(r)


@router.put("/requirements/{req_id}")
def update_requirement(req_id: int, data: dict, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    r = db.query(ComplianceRequirement).filter(ComplianceRequirement.id == req_id).first()
    if not r:
        raise HTTPException(404, "Requirement not found")
    for k, v in data.items():
        if hasattr(r, k) and k not in ("id",):
            setattr(r, k, v)
    db.commit()
    db.refresh(r)
    return _dict(r)


# --- Document Types ---
@router.get("/document-types")
def list_document_types(db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    items = db.query(DocumentType).all()
    return {"total": len(items), "items": [_dict(x) for x in items]}


@router.post("/document-types", status_code=201)
def create_document_type(data: dict, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    dt = DocumentType(**{k: v for k, v in data.items() if hasattr(DocumentType, k)})
    db.add(dt)
    db.commit()
    db.refresh(dt)
    return _dict(dt)


@router.put("/document-types/{dt_id}")
def update_document_type(dt_id: int, data: dict, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    dt = db.query(DocumentType).filter(DocumentType.id == dt_id).first()
    if not dt:
        raise HTTPException(404, "Document type not found")
    for k, v in data.items():
        if hasattr(dt, k) and k not in ("id",):
            setattr(dt, k, v)
    db.commit()
    db.refresh(dt)
    return _dict(dt)


@router.delete("/document-types/{dt_id}")
def delete_document_type(dt_id: int, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    dt = db.query(DocumentType).filter(DocumentType.id == dt_id).first()
    if not dt:
        raise HTTPException(404, "Document type not found")
    db.delete(dt)
    db.commit()
    return {"message": "Document type deleted"}


# --- Documents ---
@router.get("/documents")
def list_documents(expiry_before: Optional[date] = None, db: Session = Depends(get_db),
                   user: UserAccount = Depends(get_current_user)):
    q = db.query(Document)
    if expiry_before:
        q = q.filter(Document.expiry_date <= expiry_before)
    if user.tenant_org_id:
        q = q.filter(Document.tenant_org_id == user.tenant_org_id)
    items = q.all()
    return {"total": len(items), "items": [_dict(x) for x in items]}


@router.post("/documents", status_code=201)
def create_document(data: dict, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    doc = Document(**{k: v for k, v in data.items() if hasattr(Document, k)})
    if user.tenant_org_id:
        doc.tenant_org_id = user.tenant_org_id
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return _dict(doc)


# --- Inspections ---
@router.get("/inspections")
def list_inspections(status: Optional[str] = None, db: Session = Depends(get_db),
                     user: UserAccount = Depends(get_current_user)):
    q = db.query(Inspection)
    if status:
        q = q.filter(Inspection.status == status)
    if user.tenant_org_id:
        q = q.filter(Inspection.tenant_org_id == user.tenant_org_id)
    items = q.all()
    return {"total": len(items), "items": [_dict(x) for x in items]}


@router.post("/inspections", status_code=201)
def create_inspection(data: dict, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    i = Inspection(**{k: v for k, v in data.items() if hasattr(Inspection, k)})
    if user.tenant_org_id:
        i.tenant_org_id = user.tenant_org_id
    db.add(i)
    db.commit()
    db.refresh(i)
    return _dict(i)


@router.put("/inspections/{insp_id}")
def update_inspection(insp_id: int, data: dict, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    i = db.query(Inspection).filter(Inspection.id == insp_id).first()
    if not i:
        raise HTTPException(404, "Inspection not found")
    for k, v in data.items():
        if hasattr(i, k) and k not in ("id",):
            setattr(i, k, v)
    db.commit()
    db.refresh(i)
    return _dict(i)


# --- Compliance Items ---
@router.get("/items")
def list_compliance_items(status: Optional[str] = None, entity_type: Optional[str] = None,
                          db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    q = db.query(ComplianceItem)
    if status:
        q = q.filter(ComplianceItem.status == status)
    if entity_type:
        q = q.filter(ComplianceItem.entity_type == entity_type)
    items = q.all()
    return {"total": len(items), "items": [_dict(x) for x in items]}


@router.post("/items", status_code=201)
def create_compliance_item(data: dict, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    ci = ComplianceItem(**{k: v for k, v in data.items() if hasattr(ComplianceItem, k)})
    db.add(ci)
    db.commit()
    db.refresh(ci)
    return _dict(ci)


@router.put("/items/{item_id}")
def update_compliance_item(item_id: int, data: dict, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    ci = db.query(ComplianceItem).filter(ComplianceItem.id == item_id).first()
    if not ci:
        raise HTTPException(404, "Compliance item not found")
    for k, v in data.items():
        if hasattr(ci, k) and k not in ("id",):
            setattr(ci, k, v)
    db.commit()
    db.refresh(ci)
    return _dict(ci)


def _dict(obj):
    return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}
