"""Maintenance routes – requests, work orders, SLA, attachments, resources."""
import logging
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional
from app.database import get_db
from app.auth.dependencies import get_current_user, require_permissions
from app.auth.models import UserAccount
from app.modules.maintenance.models import (
    MaintenanceRequest, WorkOrder, MaintenanceSLA, MaintenanceAttachment,
    Resource, ResourceAllocation, ConsumableRequest, TenantFeedback
)
from app.utils.event_service import emit_outbox_event

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
    # Sanitize int fields
    for fld in ("property_id", "unit_id", "tenant_id"):
        if fld in data:
            data[fld] = int(data[fld]) if data[fld] else None
    req = MaintenanceRequest(**{k: v for k, v in data.items() if hasattr(MaintenanceRequest, k)})
    if user.tenant_org_id:
        req.tenant_org_id = user.tenant_org_id
    db.add(req)
    db.flush()
    emit_outbox_event(
        db=db,
        tenant_org_id=user.tenant_org_id,
        event_type="maintenance.request.created",
        aggregate_type="MaintenanceRequest",
        aggregate_id=req.id,
        payload={
            "property_id": req.property_id,
            "unit_id": req.unit_id,
            "tenant_id": req.tenant_id,
            "priority": req.priority,
            "status": req.status,
        },
        event_key=f"maintenance.request.created.{req.id}",
    )
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
    db.flush()
    emit_outbox_event(
        db=db,
        tenant_org_id=user.tenant_org_id,
        event_type="maintenance.work_order.created",
        aggregate_type="WorkOrder",
        aggregate_id=wo.id,
        payload={"request_id": wo.request_id, "status": wo.status, "priority": wo.priority},
        event_key=f"maintenance.work_order.created.{wo.id}",
    )
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


# ─── Work Order Resolve (triggers feedback flow) ───
@router.put("/work-orders/{wo_id}/resolve")
def resolve_work_order(wo_id: int, data: dict, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    wo = db.query(WorkOrder).filter(WorkOrder.id == wo_id).first()
    if not wo:
        raise HTTPException(404, "Work order not found")
    wo.status = "Completed"
    wo.actual_end = datetime.utcnow()
    if data.get("notes"):
        wo.access_instructions = (wo.access_instructions or "") + f"\n[RESOLVED] {data['notes']}"
    db.commit()
    db.refresh(wo)
    return {"message": "Work order resolved", "work_order": _to_dict(wo)}


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


# ─── Resources (Resource Master) ───
@router.get("/resources")
def list_resources(resource_type: Optional[str] = None, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    q = db.query(Resource)
    if user.tenant_org_id:
        q = q.filter(Resource.tenant_org_id == user.tenant_org_id)
    if resource_type:
        q = q.filter(Resource.resource_type == resource_type)
    items = q.order_by(Resource.id.desc()).all()
    return {"total": len(items), "items": [_to_dict(r) for r in items]}


@router.post("/resources", status_code=201)
def create_resource(data: dict, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    res = Resource(**{k: v for k, v in data.items() if hasattr(Resource, k)})
    if user.tenant_org_id:
        res.tenant_org_id = user.tenant_org_id
    db.add(res)
    db.commit()
    db.refresh(res)
    return _to_dict(res)


@router.put("/resources/{res_id}")
def update_resource(res_id: int, data: dict, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    res = db.query(Resource).filter(Resource.id == res_id).first()
    if not res:
        raise HTTPException(404, "Resource not found")
    for k, v in data.items():
        if hasattr(res, k) and k not in ("id",):
            setattr(res, k, v)
    db.commit()
    db.refresh(res)
    return _to_dict(res)


@router.delete("/resources/{res_id}")
def delete_resource(res_id: int, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    res = db.query(Resource).filter(Resource.id == res_id).first()
    if not res:
        raise HTTPException(404, "Resource not found")
    db.delete(res)
    db.commit()
    return {"message": "Resource deleted"}


# ─── Resource Allocation (Manager allocates resource to work order) ───
@router.post("/work-orders/{wo_id}/allocate", status_code=201)
def allocate_resource(wo_id: int, data: dict, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    wo = db.query(WorkOrder).filter(WorkOrder.id == wo_id).first()
    if not wo:
        raise HTTPException(404, "Work order not found")
    alloc = ResourceAllocation(
        resource_id=int(data["resource_id"]),
        work_order_id=wo_id,
        allocated_by=user.id,
    )
    db.add(alloc)
    # Update resource availability
    res = db.query(Resource).filter(Resource.id == int(data["resource_id"])).first()
    if res:
        res.availability = "Busy"
    db.commit()
    db.refresh(alloc)
    return _to_dict(alloc)


@router.get("/work-orders/{wo_id}/allocations")
def list_allocations(wo_id: int, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    items = db.query(ResourceAllocation).filter(ResourceAllocation.work_order_id == wo_id).all()
    return {"total": len(items), "items": [_to_dict(a) for a in items]}


# ─── Consumable Requests ───
@router.post("/work-orders/{wo_id}/consumables", status_code=201)
def request_consumable(wo_id: int, data: dict, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    wo = db.query(WorkOrder).filter(WorkOrder.id == wo_id).first()
    if not wo:
        raise HTTPException(404, "Work order not found")
    cr = ConsumableRequest(
        work_order_id=wo_id,
        resource_id=data.get("resource_id"),
        requested_by=user.id,
        items_description=data.get("items_description", ""),
        estimated_cost=float(data.get("estimated_cost", 0)),
    )
    db.add(cr)
    db.commit()
    db.refresh(cr)
    return _to_dict(cr)


@router.get("/work-orders/{wo_id}/consumables")
def list_consumables(wo_id: int, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    items = db.query(ConsumableRequest).filter(ConsumableRequest.work_order_id == wo_id).all()
    return {"total": len(items), "items": [_to_dict(c) for c in items]}


@router.put("/consumables/{cr_id}/approve")
def approve_consumable(cr_id: int, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    cr = db.query(ConsumableRequest).filter(ConsumableRequest.id == cr_id).first()
    if not cr:
        raise HTTPException(404, "Consumable request not found")
    cr.status = "Approved"
    cr.approved_by = user.id
    cr.approved_at = datetime.utcnow()
    db.commit()
    return {"message": "Consumable request approved"}


# ─── Tenant Feedback ───
@router.post("/work-orders/{wo_id}/feedback", status_code=201)
def submit_feedback(wo_id: int, data: dict, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    wo = db.query(WorkOrder).filter(WorkOrder.id == wo_id).first()
    if not wo:
        raise HTTPException(404, "Work order not found")
    fb = TenantFeedback(
        work_order_id=wo_id,
        tenant_id=data.get("tenant_id"),
        rating=int(data.get("rating", 0)),
        comments=data.get("comments", ""),
    )
    db.add(fb)
    db.commit()
    db.refresh(fb)
    return _to_dict(fb)


@router.get("/work-orders/{wo_id}/feedback")
def list_feedback(wo_id: int, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    items = db.query(TenantFeedback).filter(TenantFeedback.work_order_id == wo_id).all()
    return {"total": len(items), "items": [_to_dict(f) for f in items]}


def _to_dict(obj):
    return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}
