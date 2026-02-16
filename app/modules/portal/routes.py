"""Portal routes for tenant, owner, and vendor views."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional
from app.database import get_db
from app.auth.dependencies import get_current_user, require_permissions
from app.auth.models import UserAccount
from app.modules.properties.models import Tenant, Owner, Vendor, Property, PropertyOwnerLink
from app.modules.leasing.models import Lease, LeaseDocument
from app.modules.billing.models import Invoice, Payment
from app.modules.maintenance.models import MaintenanceRequest, WorkOrder, WorkOrderTimeEntry
from app.modules.compliance.models import Document
from app.modules.accounting.models import OwnerDistribution, OwnerStatement, VendorInvoice

router = APIRouter(
    prefix="/api/portal",
    tags=["Portal"],
    dependencies=[Depends(require_permissions(["portal", "lease", "payments", "work_orders", "portfolio"]))],
)


def _dict(obj):
    return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}


def _resolve_entity_id(user: UserAccount, expected_type: str, entity_id: Optional[int]) -> int:
    if user.linked_entity_type == expected_type and user.linked_entity_id:
        return user.linked_entity_id
    if user.role_id in (1, 2) and entity_id:
        return entity_id
    raise HTTPException(status_code=403, detail=f"Not linked to {expected_type}")


@router.get("/tenant/overview")
def tenant_overview(entity_id: Optional[int] = Query(default=None), db: Session = Depends(get_db),
                    user: UserAccount = Depends(get_current_user)):
    tenant_id = _resolve_entity_id(user, "Tenant", entity_id)
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    if user.tenant_org_id and tenant.tenant_org_id != user.tenant_org_id:
        raise HTTPException(status_code=403, detail="Cross-org access denied")

    leases = db.query(Lease).filter(Lease.tenant_id == tenant_id).order_by(Lease.id.desc()).all()
    invoices = db.query(Invoice).filter(Invoice.tenant_id == tenant_id).order_by(Invoice.id.desc()).limit(50).all()
    payments = db.query(Payment).filter(Payment.tenant_id == tenant_id).order_by(Payment.id.desc()).limit(50).all()
    requests = db.query(MaintenanceRequest).filter(MaintenanceRequest.tenant_id == tenant_id).order_by(
        MaintenanceRequest.id.desc()).limit(50).all()
    docs = db.query(Document).filter(
        Document.owner_entity_type == "Tenant",
        Document.owner_entity_id == tenant_id,
    ).order_by(Document.id.desc()).all()
    lease_docs = db.query(LeaseDocument).join(Lease, LeaseDocument.lease_id == Lease.id).filter(
        Lease.tenant_id == tenant_id
    ).order_by(LeaseDocument.id.desc()).all()

    return {
        "tenant": _dict(tenant),
        "leases": [_dict(l) for l in leases],
        "invoices": [_dict(i) for i in invoices],
        "payments": [_dict(p) for p in payments],
        "maintenance_requests": [_dict(r) for r in requests],
        "documents": [_dict(d) for d in docs],
        "lease_documents": [_dict(d) for d in lease_docs],
    }


@router.get("/owner/overview")
def owner_overview(entity_id: Optional[int] = Query(default=None), db: Session = Depends(get_db),
                   user: UserAccount = Depends(get_current_user)):
    owner_id = _resolve_entity_id(user, "Owner", entity_id)
    owner = db.query(Owner).filter(Owner.id == owner_id).first()
    if not owner:
        raise HTTPException(status_code=404, detail="Owner not found")
    if user.tenant_org_id and owner.tenant_org_id != user.tenant_org_id:
        raise HTTPException(status_code=403, detail="Cross-org access denied")

    links = db.query(PropertyOwnerLink).filter(PropertyOwnerLink.owner_id == owner_id).all()
    prop_ids = [l.property_id for l in links]
    properties = db.query(Property).filter(Property.id.in_(prop_ids)).all() if prop_ids else []
    distributions = db.query(OwnerDistribution).filter(OwnerDistribution.owner_id == owner_id).order_by(
        OwnerDistribution.id.desc()).limit(50).all()
    statements = db.query(OwnerStatement).filter(OwnerStatement.owner_id == owner_id).order_by(
        OwnerStatement.id.desc()).limit(20).all()
    docs = db.query(Document).filter(
        Document.owner_entity_type == "Owner",
        Document.owner_entity_id == owner_id,
    ).order_by(Document.id.desc()).all()

    return {
        "owner": _dict(owner),
        "properties": [_dict(p) for p in properties],
        "ownerships": [_dict(l) for l in links],
        "distributions": [_dict(d) for d in distributions],
        "statements": [_dict(s) for s in statements],
        "documents": [_dict(d) for d in docs],
    }


@router.get("/vendor/overview")
def vendor_overview(entity_id: Optional[int] = Query(default=None), db: Session = Depends(get_db),
                    user: UserAccount = Depends(get_current_user)):
    vendor_id = _resolve_entity_id(user, "Vendor", entity_id)
    vendor = db.query(Vendor).filter(Vendor.id == vendor_id).first()
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")
    if user.tenant_org_id and vendor.tenant_org_id != user.tenant_org_id:
        raise HTTPException(status_code=403, detail="Cross-org access denied")

    work_orders = db.query(WorkOrder).filter(WorkOrder.assigned_vendor_id == vendor_id).order_by(
        WorkOrder.id.desc()).limit(50).all()
    time_entries = db.query(WorkOrderTimeEntry).filter(WorkOrderTimeEntry.vendor_id == vendor_id).order_by(
        WorkOrderTimeEntry.id.desc()).limit(100).all()
    invoices = db.query(VendorInvoice).filter(VendorInvoice.vendor_id == vendor_id).order_by(
        VendorInvoice.id.desc()).limit(50).all()
    docs = db.query(Document).filter(
        Document.owner_entity_type == "Vendor",
        Document.owner_entity_id == vendor_id,
    ).order_by(Document.id.desc()).all()

    return {
        "vendor": _dict(vendor),
        "work_orders": [_dict(w) for w in work_orders],
        "time_entries": [_dict(t) for t in time_entries],
        "invoices": [_dict(i) for i in invoices],
        "documents": [_dict(d) for d in docs],
    }
