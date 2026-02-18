"""Compliance API routes – requirements, documents, inspections, compliance items."""
import os
import shutil
from datetime import date, datetime
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException, File, Form, UploadFile
from sqlalchemy.orm import Session
from typing import Optional
from app.database import get_db
from app.auth.dependencies import get_current_user, require_permissions
from app.auth.models import UserAccount
from app.config import get_settings
from app.modules.compliance.models import (
    ComplianceRequirement, Document, DocumentType, Inspection, ComplianceItem
)

router = APIRouter(
    prefix="/api/compliance",
    tags=["Compliance"],
    dependencies=[Depends(require_permissions(["compliance", "portfolio"]))],
)
settings = get_settings()


def _parse_iso_date(value, field_name: str) -> Optional[date]:
    if value in (None, ""):
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError:
            raise HTTPException(400, f"Invalid date for '{field_name}'. Expected YYYY-MM-DD")
    raise HTTPException(400, f"Invalid value for '{field_name}'. Expected YYYY-MM-DD")


def _sanitize_requirement_data(data: dict) -> dict:
    clean = {}
    for k, v in data.items():
        if not hasattr(ComplianceRequirement, k) or k in ("id", "created_at"):
            continue
        if v in ("", None):
            clean[k] = None
        elif k in {"document_type_id", "tenant_org_id"}:
            try:
                clean[k] = int(v)
            except (TypeError, ValueError):
                clean[k] = None
        elif k == "is_active":
            clean[k] = v if isinstance(v, bool) else str(v).lower() in ("1", "true", "yes", "on")
        else:
            clean[k] = v
    return clean


def _sanitize_document_data(data: dict) -> dict:
    clean = {}
    int_fields = {"owner_entity_id", "document_type_id", "version_number", "tenant_org_id"}
    bool_fields = {"is_signed"}
    date_fields = {"expiry_date"}
    for k, v in data.items():
        if not hasattr(Document, k) or k in ("id", "created_at", "upload_date"):
            continue
        if v in ("", None):
            clean[k] = None
        elif k in int_fields:
            try:
                clean[k] = int(v)
            except (TypeError, ValueError):
                clean[k] = None
        elif k in bool_fields:
            clean[k] = v if isinstance(v, bool) else str(v).lower() in ("1", "true", "yes", "on")
        elif k in date_fields:
            clean[k] = _parse_iso_date(v, k)
        else:
            clean[k] = v
    return clean


def _sanitize_inspection_data(data: dict) -> dict:
    clean = {}
    int_fields = {"property_id", "unit_id", "inspector_id", "tenant_org_id"}
    date_fields = {"scheduled_date", "completed_date"}
    for k, v in data.items():
        if not hasattr(Inspection, k) or k in ("id", "created_at", "updated_at"):
            continue
        if v in ("", None):
            clean[k] = None
        elif k in int_fields:
            try:
                clean[k] = int(v)
            except (TypeError, ValueError):
                clean[k] = None
        elif k in date_fields:
            clean[k] = _parse_iso_date(v, k)
        else:
            clean[k] = v
    return clean


def _sanitize_compliance_item_data(data: dict) -> dict:
    clean = {}
    int_fields = {"requirement_id", "entity_id", "escalation_level"}
    date_fields = {"due_date"}
    for k, v in data.items():
        if not hasattr(ComplianceItem, k) or k in ("id", "created_at", "updated_at"):
            continue
        if v in ("", None):
            clean[k] = None
        elif k in int_fields:
            try:
                clean[k] = int(v)
            except (TypeError, ValueError):
                clean[k] = None
        elif k in date_fields:
            clean[k] = _parse_iso_date(v, k)
        else:
            clean[k] = v
    return clean


def _compliance_upload_dir() -> str:
    upload_dir = settings.UPLOAD_DIR
    if not os.path.isabs(upload_dir):
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
        upload_dir = os.path.join(project_root, upload_dir)
    return os.path.abspath(upload_dir)


def _document_query_for_user(db: Session, user: UserAccount):
    q = db.query(Document)
    if user.tenant_org_id:
        q = q.filter(Document.tenant_org_id == user.tenant_org_id)
    return q


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
    clean = _sanitize_requirement_data(data)
    if not clean.get("requirement_name"):
        raise HTTPException(400, "Field 'requirement_name' is required")
    r = ComplianceRequirement(**clean)
    if user.tenant_org_id:
        r.tenant_org_id = user.tenant_org_id
    db.add(r)
    db.commit()
    db.refresh(r)
    return _dict(r)


@router.put("/requirements/{req_id}")
def update_requirement(req_id: int, data: dict, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    q = db.query(ComplianceRequirement).filter(ComplianceRequirement.id == req_id)
    if user.tenant_org_id:
        q = q.filter(ComplianceRequirement.tenant_org_id == user.tenant_org_id)
    r = q.first()
    if not r:
        raise HTTPException(404, "Requirement not found")
    clean = _sanitize_requirement_data(data)
    for k, v in clean.items():
        if hasattr(r, k) and k not in ("id",):
            setattr(r, k, v)
    db.commit()
    db.refresh(r)
    return _dict(r)


@router.delete("/requirements/{req_id}")
def delete_requirement(req_id: int, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    q = db.query(ComplianceRequirement).filter(ComplianceRequirement.id == req_id)
    if user.tenant_org_id:
        q = q.filter(ComplianceRequirement.tenant_org_id == user.tenant_org_id)
    r = q.first()
    if not r:
        raise HTTPException(404, "Requirement not found")
    db.delete(r)
    db.commit()
    return {"message": "Requirement deleted"}


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
    q = _document_query_for_user(db, user)
    if expiry_before:
        q = q.filter(Document.expiry_date <= expiry_before)
    items = q.order_by(Document.id.desc()).all()
    return {"total": len(items), "items": [_dict(x) for x in items]}


@router.post("/documents", status_code=201)
def create_document(data: dict, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    clean = _sanitize_document_data(data)
    if not clean.get("owner_entity_type"):
        raise HTTPException(400, "Field 'owner_entity_type' is required")
    if not clean.get("owner_entity_id"):
        raise HTTPException(400, "Field 'owner_entity_id' is required")
    if not clean.get("file_name") and clean.get("file_path"):
        clean["file_name"] = os.path.basename(str(clean["file_path"]))
    if not clean.get("file_name"):
        raise HTTPException(400, "Field 'file_name' is required")

    doc = Document(**clean)
    if user.tenant_org_id:
        doc.tenant_org_id = user.tenant_org_id
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return _dict(doc)


@router.post("/documents/upload", status_code=201)
async def upload_document(
    owner_entity_type: str = Form(...),
    owner_entity_id: int = Form(...),
    file: UploadFile = File(...),
    document_type_id: Optional[int] = Form(None),
    expiry_date: Optional[str] = Form(None),
    is_signed: Optional[bool] = Form(False),
    db: Session = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    safe_name = os.path.basename(file.filename or "document")
    ext = os.path.splitext(safe_name)[1]
    stored_name = f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{uuid4().hex[:8]}{ext}"
    tenant_folder = str(user.tenant_org_id) if user.tenant_org_id else "global"

    upload_root = _compliance_upload_dir()
    save_dir = os.path.join(upload_root, "compliance", tenant_folder)
    os.makedirs(save_dir, exist_ok=True)

    absolute_path = os.path.join(save_dir, stored_name)
    with open(absolute_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    doc = Document(
        tenant_org_id=user.tenant_org_id,
        owner_entity_type=owner_entity_type,
        owner_entity_id=owner_entity_id,
        document_type_id=document_type_id,
        file_name=safe_name,
        file_path=f"/uploads/compliance/{tenant_folder}/{stored_name}",
        mime_type=file.content_type,
        expiry_date=_parse_iso_date(expiry_date, "expiry_date"),
        is_signed=bool(is_signed),
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return _dict(doc)


@router.delete("/documents/{doc_id}")
def delete_document(doc_id: int, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    doc = _document_query_for_user(db, user).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(404, "Document not found")

    if doc.file_path and isinstance(doc.file_path, str) and doc.file_path.startswith("/uploads/"):
        upload_root = _compliance_upload_dir()
        relative_path = doc.file_path.replace("/uploads/", "", 1)
        absolute_path = os.path.abspath(os.path.join(upload_root, relative_path))
        if absolute_path.startswith(upload_root) and os.path.exists(absolute_path):
            os.remove(absolute_path)

    db.delete(doc)
    db.commit()
    return {"message": "Document deleted"}


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
    clean = _sanitize_inspection_data(data)
    i = Inspection(**clean)
    if user.tenant_org_id:
        i.tenant_org_id = user.tenant_org_id
    db.add(i)
    db.commit()
    db.refresh(i)
    return _dict(i)


@router.put("/inspections/{insp_id}")
def update_inspection(insp_id: int, data: dict, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    q = db.query(Inspection).filter(Inspection.id == insp_id)
    if user.tenant_org_id:
        q = q.filter(Inspection.tenant_org_id == user.tenant_org_id)
    i = q.first()
    if not i:
        raise HTTPException(404, "Inspection not found")
    clean = _sanitize_inspection_data(data)
    for k, v in clean.items():
        if hasattr(i, k) and k not in ("id",):
            setattr(i, k, v)
    db.commit()
    db.refresh(i)
    return _dict(i)


@router.delete("/inspections/{insp_id}")
def delete_inspection(insp_id: int, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    q = db.query(Inspection).filter(Inspection.id == insp_id)
    if user.tenant_org_id:
        q = q.filter(Inspection.tenant_org_id == user.tenant_org_id)
    i = q.first()
    if not i:
        raise HTTPException(404, "Inspection not found")
    db.delete(i)
    db.commit()
    return {"message": "Inspection deleted"}


# --- Compliance Items ---
@router.get("/items")
def list_compliance_items(status: Optional[str] = None, entity_type: Optional[str] = None,
                          db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    q = db.query(ComplianceItem)
    if status:
        q = q.filter(ComplianceItem.status == status)
    if entity_type:
        q = q.filter(ComplianceItem.entity_type == entity_type)
    if user.tenant_org_id:
        q = q.join(ComplianceRequirement, ComplianceItem.requirement_id == ComplianceRequirement.id).filter(
            ComplianceRequirement.tenant_org_id == user.tenant_org_id
        )
    items = q.all()
    return {"total": len(items), "items": [_dict(x) for x in items]}


@router.post("/items", status_code=201)
def create_compliance_item(data: dict, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    clean = _sanitize_compliance_item_data(data)
    if not clean.get("requirement_id"):
        raise HTTPException(400, "Field 'requirement_id' is required")
    ci = ComplianceItem(**clean)
    db.add(ci)
    db.commit()
    db.refresh(ci)
    return _dict(ci)


@router.put("/items/{item_id}")
def update_compliance_item(item_id: int, data: dict, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    ci = db.query(ComplianceItem).filter(ComplianceItem.id == item_id).first()
    if not ci:
        raise HTTPException(404, "Compliance item not found")
    clean = _sanitize_compliance_item_data(data)
    for k, v in clean.items():
        if hasattr(ci, k) and k not in ("id",):
            setattr(ci, k, v)
    db.commit()
    db.refresh(ci)
    return _dict(ci)


def _dict(obj):
    return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}
