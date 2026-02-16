"""Maintenance routes – requests, work orders, SLA, attachments."""
import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional
from app.database import get_db
from app.auth.dependencies import get_current_user, require_permissions
from app.auth.models import UserAccount
from app.modules.maintenance.models import (
    MaintenanceRequest, WorkOrder, MaintenanceSLA, MaintenanceAttachment
)

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/api/maintenance",
    tags=["Maintenance"],
    dependencies=[Depends(require_permissions(["maintenance", "work_orders", "portfolio"]))],
)


# ─── Requests ───
@router.get("/requests")
def list_requests(status: Optional[str] = None, priority: Optional[str] = None,
                  property_id: Optional[int] = None, skip: int = 0, limit: int = 50,
                  db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    q = db.query(MaintenanceRequest)
    if user.tenant_org_id:
        q = q.filter(MaintenanceRequest.tenant_org_id == user.tenant_org_id)
    if status:
        q = q.filter(MaintenanceRequest.status == status)
    if priority:
        q = q.filter(MaintenanceRequest.priority == priority)
    if property_id:
        q = q.filter(MaintenanceRequest.property_id == property_id)
    total = q.count()
    items = q.order_by(MaintenanceRequest.id.desc()).offset(skip).limit(limit).all()
    return {"total": total, "items": [_to_dict(r) for r in items]}


@router.post("/requests", status_code=201)
def create_request(data: dict, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    req = MaintenanceRequest(**{k: v for k, v in data.items() if hasattr(MaintenanceRequest, k)})
    if user.tenant_org_id:
        req.tenant_org_id = user.tenant_org_id
    db.add(req)
    db.commit()
    db.refresh(req)
    return _to_dict(req)


@router.get("/requests/{req_id}")
def get_request(req_id: int, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    req = db.query(MaintenanceRequest).filter(MaintenanceRequest.id == req_id).first()
    if not req:
        raise HTTPException(404, "Request not found")
    d = _to_dict(req)
    d["work_orders"] = [_to_dict(wo) for wo in db.query(WorkOrder).filter(WorkOrder.request_id == req_id).all()]
    return d


@router.put("/requests/{req_id}")
def update_request(req_id: int, data: dict, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    req = db.query(MaintenanceRequest).filter(MaintenanceRequest.id == req_id).first()
    if not req:
        raise HTTPException(404, "Request not found")
    for k, v in data.items():
        if hasattr(req, k) and k not in ("id",):
            setattr(req, k, v)
    db.commit()
    db.refresh(req)
    return _to_dict(req)


@router.post("/requests/{req_id}/escalate")
def escalate_request(req_id: int, data: dict, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    req = db.query(MaintenanceRequest).filter(MaintenanceRequest.id == req_id).first()
    if not req:
        raise HTTPException(404, "Request not found")
    req.priority = "Critical"
    req.status = "Escalated"
    if data.get("notes"):
        req.resolution_notes = (req.resolution_notes or "") + f"\n[ESCALATED] {data['notes']}"
    db.commit()
    return {"message": "Request escalated", "request_id": req_id}


# ─── Work Orders ───
@router.get("/work-orders")
def list_work_orders(status: Optional[str] = None, skip: int = 0, limit: int = 50,
                     db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    q = db.query(WorkOrder)
    if user.tenant_org_id:
        q = q.filter(WorkOrder.tenant_org_id == user.tenant_org_id)
    if status:
        q = q.filter(WorkOrder.status == status)
    total = q.count()
    items = q.order_by(WorkOrder.id.desc()).offset(skip).limit(limit).all()
    return {"total": total, "items": [_to_dict(wo) for wo in items]}


@router.post("/work-orders", status_code=201)
def create_work_order(data: dict, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    wo = WorkOrder(**{k: v for k, v in data.items() if hasattr(WorkOrder, k)})
    if user.tenant_org_id:
        wo.tenant_org_id = user.tenant_org_id
    db.add(wo)
    db.commit()
    db.refresh(wo)
    return _to_dict(wo)


@router.get("/work-orders/{wo_id}")
def get_work_order(wo_id: int, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    wo = db.query(WorkOrder).filter(WorkOrder.id == wo_id).first()
    if not wo:
        raise HTTPException(404, "Work order not found")
    return _to_dict(wo)


@router.put("/work-orders/{wo_id}")
def update_work_order(wo_id: int, data: dict, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    wo = db.query(WorkOrder).filter(WorkOrder.id == wo_id).first()
    if not wo:
        raise HTTPException(404, "Work order not found")
    for k, v in data.items():
        if hasattr(wo, k) and k not in ("id",):
            setattr(wo, k, v)
    db.commit()
    db.refresh(wo)
    return _to_dict(wo)


@router.delete("/work-orders/{wo_id}")
def delete_work_order(wo_id: int, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    wo = db.query(WorkOrder).filter(WorkOrder.id == wo_id).first()
    if not wo:
        raise HTTPException(404, "Work order not found")
    db.delete(wo)
    db.commit()
    return {"message": "Work order deleted"}


# ─── SLA Rules ───
@router.get("/sla-rules")
def list_sla_rules(db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    items = db.query(MaintenanceSLA).all()
    return {"total": len(items), "items": [_to_dict(s) for s in items]}


@router.post("/sla-rules", status_code=201)
def create_sla_rule(data: dict, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    sla = MaintenanceSLA(**{k: v for k, v in data.items() if hasattr(MaintenanceSLA, k)})
    if user.tenant_org_id:
        sla.tenant_org_id = user.tenant_org_id
    db.add(sla)
    db.commit()
    db.refresh(sla)
    return _to_dict(sla)


@router.put("/sla-rules/{sla_id}")
def update_sla_rule(sla_id: int, data: dict, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    sla = db.query(MaintenanceSLA).filter(MaintenanceSLA.id == sla_id).first()
    if not sla:
        raise HTTPException(404, "SLA rule not found")
    for k, v in data.items():
        if hasattr(sla, k) and k not in ("id",):
            setattr(sla, k, v)
    db.commit()
    db.refresh(sla)
    return _to_dict(sla)


@router.delete("/sla-rules/{sla_id}")
def delete_sla_rule(sla_id: int, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    sla = db.query(MaintenanceSLA).filter(MaintenanceSLA.id == sla_id).first()
    if not sla:
        raise HTTPException(404, "SLA rule not found")
    db.delete(sla)
    db.commit()
    return {"message": "SLA rule deleted"}


# ─── Attachments ───
@router.get("/requests/{req_id}/attachments")
def list_attachments(req_id: int, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    items = db.query(MaintenanceAttachment).filter(MaintenanceAttachment.request_id == req_id).all()
    return {"total": len(items), "items": [_to_dict(a) for a in items]}


@router.post("/requests/{req_id}/attachments", status_code=201)
def create_attachment(req_id: int, data: dict, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    att = MaintenanceAttachment(**{k: v for k, v in data.items() if hasattr(MaintenanceAttachment, k)})
    att.request_id = req_id
    db.add(att)
    db.commit()
    db.refresh(att)
    return _to_dict(att)


def _to_dict(obj):
    return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}
