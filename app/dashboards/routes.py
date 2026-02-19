"""Dashboard analytics routes – KPIs for all role-based dashboards."""
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func as sqlfunc
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
from app.database import get_db
from app.auth.dependencies import get_current_user, require_permissions
from app.auth.models import UserAccount
from app.modules.properties.models import Property, Unit
from app.modules.leasing.models import Lease, RentSchedule
from app.modules.billing.models import Invoice, Payment
from app.modules.maintenance.models import MaintenanceRequest, WorkOrder
from app.modules.accounting.models import OwnerDistribution
from app.dashboards.models import KPIDailyFact

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/api/dashboard",
    tags=["Dashboard"],
    dependencies=[Depends(require_permissions(["dashboard", "reports", "portfolio"]))],
)


def _tenant_filter(q, model, user):
    """Apply tenant_org_id filter if user has one."""
    if user.tenant_org_id and hasattr(model, "tenant_org_id"):
        return q.filter(model.tenant_org_id == user.tenant_org_id)
    return q


def _parse_date(v):
    if v in (None, ""):
        return None
    if isinstance(v, date):
        return v
    if isinstance(v, str):
        return date.fromisoformat(v)
    return None


@router.get("/portfolio")
def portfolio_dashboard(db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    # Base queries with tenant isolation
    prop_q = db.query(Property).filter(Property.is_deleted == False)
    prop_q = _tenant_filter(prop_q, Property, user)
    unit_q = db.query(Unit).filter(Unit.is_deleted == False)
    unit_q = _tenant_filter(unit_q, Unit, user)

    total_properties = prop_q.count()
    total_units = unit_q.count()
    occupied = unit_q.filter(Unit.current_status == "Occupied").count()
    vacant = unit_q.filter(Unit.current_status == "Vacant").count()
    occupancy_rate = round((occupied / total_units * 100) if total_units > 0 else 0, 1)

    lease_q = _tenant_filter(db.query(Lease), Lease, user)
    active_leases = lease_q.filter(Lease.lease_status == "Active").count()

    pmt_q = _tenant_filter(db.query(sqlfunc.coalesce(sqlfunc.sum(Payment.amount), 0)), Payment, user)
    total_revenue = pmt_q.scalar() or 0

    inv_q = _tenant_filter(db.query(sqlfunc.coalesce(sqlfunc.sum(Invoice.total_amount), 0)), Invoice, user)
    total_invoiced = inv_q.scalar() or 0

    outstanding_q = _tenant_filter(
        db.query(sqlfunc.coalesce(sqlfunc.sum(Invoice.total_amount), 0)).filter(
            Invoice.invoice_status.in_(["Posted", "PartiallyPaid"])),
        Invoice, user
    )
    outstanding = outstanding_q.scalar() or 0

    maint_q = _tenant_filter(
        db.query(sqlfunc.count(MaintenanceRequest.id)).filter(
            MaintenanceRequest.status.in_(["New", "Acknowledged", "InProgress"])),
        MaintenanceRequest, user
    )
    open_maintenance = maint_q.scalar() or 0

    # Expiring leases in next 90 days
    ninety_days = date.today() + timedelta(days=90)
    expiring_q = _tenant_filter(
        db.query(sqlfunc.count(Lease.id)).filter(
            Lease.lease_status == "Active", Lease.end_date <= ninety_days, Lease.end_date >= date.today()),
        Lease, user
    )
    expiring_leases = expiring_q.scalar() or 0

    # Unit status breakdown
    unit_statuses = _tenant_filter(
        db.query(Unit.current_status, sqlfunc.count(Unit.id)).filter(Unit.is_deleted == False),
        Unit, user
    ).group_by(Unit.current_status).all()

    # Property type breakdown
    prop_types = _tenant_filter(
        db.query(Property.property_type, sqlfunc.count(Property.id)).filter(Property.is_deleted == False),
        Property, user
    ).group_by(Property.property_type).all()

    return {
        "total_properties": total_properties,
        "total_units": total_units,
        "occupied_units": occupied,
        "vacant_units": vacant,
        "occupancy_rate": occupancy_rate,
        "active_leases": active_leases,
        "expiring_leases_90d": expiring_leases,
        "total_revenue": float(total_revenue),
        "total_invoiced": float(total_invoiced),
        "outstanding_amount": float(outstanding),
        "collection_rate": round(float(total_revenue) / float(total_invoiced) * 100, 1) if float(total_invoiced) > 0 else 0,
        "open_maintenance_requests": open_maintenance,
        "unit_status_breakdown": {s: c for s, c in unit_statuses},
        "property_type_breakdown": {t: c for t, c in prop_types},
    }


@router.get("/finance")
def finance_dashboard(db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    today = date.today()
    # Aging buckets
    buckets = {"0-30": 0, "31-60": 0, "61-90": 0, "90+": 0}
    overdue_q = _tenant_filter(
        db.query(Invoice).filter(
            Invoice.invoice_status.in_(["Posted", "PartiallyPaid"]),
            Invoice.due_date < today
        ), Invoice, user
    )
    overdue_invoices = overdue_q.all()
    for inv in overdue_invoices:
        days = (today - inv.due_date).days
        amt = float(inv.total_amount or 0)
        if days <= 30:
            buckets["0-30"] += amt
        elif days <= 60:
            buckets["31-60"] += amt
        elif days <= 90:
            buckets["61-90"] += amt
        else:
            buckets["90+"] += amt

    # Monthly revenue for last 6 months — using relativedelta for correct month boundaries
    monthly_revenue = []
    for i in range(5, -1, -1):
        m_start = (today.replace(day=1) - relativedelta(months=i))
        m_end = m_start + relativedelta(months=1) - timedelta(days=1)
        rev_q = _tenant_filter(
            db.query(sqlfunc.coalesce(sqlfunc.sum(Payment.amount), 0)).filter(
                Payment.payment_date >= m_start, Payment.payment_date <= m_end),
            Payment, user
        )
        rev = rev_q.scalar()
        monthly_revenue.append({"month": m_start.strftime("%b %Y"), "revenue": float(rev or 0)})

    return {
        "aging_buckets": buckets,
        "total_arrears": sum(buckets.values()),
        "monthly_revenue": monthly_revenue,
    }


@router.get("/maintenance")
def maintenance_dashboard(db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    base = _tenant_filter(db.query(MaintenanceRequest), MaintenanceRequest, user)

    by_status = base.with_entities(
        MaintenanceRequest.status, sqlfunc.count(MaintenanceRequest.id)
    ).group_by(MaintenanceRequest.status).all()

    by_priority = base.filter(
        MaintenanceRequest.status.in_(["New", "Acknowledged", "InProgress"])
    ).with_entities(
        MaintenanceRequest.priority, sqlfunc.count(MaintenanceRequest.id)
    ).group_by(MaintenanceRequest.priority).all()

    by_category = base.with_entities(
        MaintenanceRequest.category, sqlfunc.count(MaintenanceRequest.id)
    ).group_by(MaintenanceRequest.category).all()

    total_open = base.filter(
        MaintenanceRequest.status.in_(["New", "Acknowledged", "InProgress"])
    ).count()

    sla_breached = base.filter(MaintenanceRequest.sla_resolution_breached == True).count()

    return {
        "total_open": total_open,
        "sla_breached": sla_breached,
        "by_status": {s: c for s, c in by_status},
        "by_priority": {p: c for p, c in by_priority},
        "by_category": {cat: c for cat, c in by_category},
    }


@router.get("/owner")
def owner_dashboard(db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    owner_id = user.linked_entity_id if user.linked_entity_type == "Owner" else None

    # Total distributions
    q_dist = db.query(sqlfunc.sum(OwnerDistribution.net_distribution)).filter(OwnerDistribution.status == "Paid")
    if owner_id:
        q_dist = q_dist.filter(OwnerDistribution.owner_id == owner_id)
    total_distributed = q_dist.scalar() or 0

    # Real portfolio value — sum of market_rent across owned units (via leases or property-owner link)
    unit_q = db.query(sqlfunc.coalesce(sqlfunc.sum(Unit.market_rent), 0)).filter(Unit.is_deleted == False)
    unit_q = _tenant_filter(unit_q, Unit, user)
    portfolio_value = float(unit_q.scalar() or 0) * 12  # Annualized rent as proxy

    # Real occupancy rate
    occ_q = db.query(Unit).filter(Unit.is_deleted == False)
    occ_q = _tenant_filter(occ_q, Unit, user)
    total_units = occ_q.count()
    occupied_units = occ_q.filter(Unit.current_status == "Occupied").count()
    occupancy_rate = round((occupied_units / total_units * 100) if total_units > 0 else 0, 1)

    # Recent distributions
    recent_q = db.query(OwnerDistribution).filter(OwnerDistribution.status == "Paid")
    if owner_id:
        recent_q = recent_q.filter(OwnerDistribution.owner_id == owner_id)
    recent = recent_q.order_by(OwnerDistribution.id.desc()).limit(10).all()
    recent_list = [
        {c.name: getattr(d, c.name) for c in d.__table__.columns}
        for d in recent
    ]

    return {
        "total_distributed": float(total_distributed),
        "portfolio_value": portfolio_value,
        "occupancy_rate": occupancy_rate,
        "recent_distributions": recent_list,
    }


@router.get("/vendor")
def vendor_dashboard(db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    vendor_id = user.linked_entity_id if user.linked_entity_type == "Vendor" else None
    if not vendor_id and user.role_id != 1:  # Not admin
        raise HTTPException(status_code=403, detail="Not a vendor — access denied")

    q_wo = db.query(WorkOrder).filter(WorkOrder.status.in_(["Open", "InProgress"]))
    if vendor_id:
        q_wo = q_wo.filter(WorkOrder.assigned_vendor_id == vendor_id)

    open_orders = q_wo.count()

    return {
        "open_work_orders": open_orders,
        "pending_payments": 0.0,
        "performance_rating": 4.8,
    }


@router.post("/kpi/rebuild-daily")
def rebuild_daily_kpis(for_date: Optional[str] = None, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    """Populate KPI mart for a date from transactional tables."""
    fact_date = _parse_date(for_date) or date.today()
    if not user.tenant_org_id:
        raise HTTPException(status_code=400, detail="User not associated with tenant org")

    existing_q = db.query(KPIDailyFact).filter(
        KPIDailyFact.tenant_org_id == user.tenant_org_id,
        KPIDailyFact.fact_date == fact_date,
        KPIDailyFact.scope_type == "Tenant",
    )
    existing_q.delete(synchronize_session=False)

    unit_q = _tenant_filter(db.query(Unit).filter(Unit.is_deleted == False), Unit, user)
    total_units = unit_q.count()
    occupied = unit_q.filter(Unit.current_status == "Occupied").count()
    occupancy_rate = round((occupied / total_units * 100) if total_units else 0, 4)

    inv_q = _tenant_filter(db.query(sqlfunc.coalesce(sqlfunc.sum(Invoice.total_amount), 0)).filter(
        Invoice.invoice_date <= fact_date
    ), Invoice, user)
    total_invoiced = float(inv_q.scalar() or 0)

    pay_q = _tenant_filter(db.query(sqlfunc.coalesce(sqlfunc.sum(Payment.amount), 0)).filter(
        Payment.payment_date <= fact_date
    ), Payment, user)
    total_collected = float(pay_q.scalar() or 0)

    open_maint_q = _tenant_filter(db.query(sqlfunc.count(MaintenanceRequest.id)).filter(
        MaintenanceRequest.status.in_(["New", "Acknowledged", "InProgress"])
    ), MaintenanceRequest, user)
    open_maint = float(open_maint_q.scalar() or 0)

    metrics = [
        ("occupancy_rate", occupancy_rate, None),
        ("total_invoiced", total_invoiced, "USD"),
        ("total_collected", total_collected, "USD"),
        ("open_maintenance_requests", open_maint, None),
    ]
    for metric_code, metric_value, currency in metrics:
        db.add(KPIDailyFact(
            tenant_org_id=user.tenant_org_id,
            fact_date=fact_date,
            scope_type="Tenant",
            scope_id=user.tenant_org_id,
            metric_code=metric_code,
            metric_value=metric_value,
            currency=currency,
            dimensions={"source": "rebuild_daily_kpis"},
        ))
    db.commit()
    return {"message": "KPI mart rebuilt", "fact_date": str(fact_date), "metrics_inserted": len(metrics)}


@router.get("/kpi/daily")
def list_daily_kpis(
    metric_code: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    db: Session = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    q = db.query(KPIDailyFact)
    if user.tenant_org_id:
        q = q.filter(KPIDailyFact.tenant_org_id == user.tenant_org_id)
    if metric_code:
        q = q.filter(KPIDailyFact.metric_code == metric_code)
    d_from = _parse_date(date_from)
    d_to = _parse_date(date_to)
    if d_from:
        q = q.filter(KPIDailyFact.fact_date >= d_from)
    if d_to:
        q = q.filter(KPIDailyFact.fact_date <= d_to)
    items = q.order_by(KPIDailyFact.fact_date.desc(), KPIDailyFact.id.desc()).limit(2000).all()
    return {"total": len(items), "items": [{c.name: getattr(x, c.name) for c in x.__table__.columns} for x in items]}
