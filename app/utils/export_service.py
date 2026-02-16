"""Export utilities - CSV and Excel exports for all major screens."""
import io
import csv
import logging
from datetime import date
from typing import Optional, Callable

from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth.dependencies import get_current_user, require_permissions
from app.auth.models import UserAccount, Role
from app.modules.properties.models import (
    Property,
    Building,
    Unit,
    Asset,
    Tenant,
    Owner,
    Vendor,
)
from app.modules.leasing.models import Lease
from app.modules.billing.models import Invoice, Payment
from app.modules.maintenance.models import MaintenanceRequest, WorkOrder
from app.modules.accounting.models import ChartOfAccount, JournalEntry, VendorBill, OwnerDistribution
from app.modules.crm.models import Contact, Task, CommunicationThread
from app.modules.marketing.models import Listing, Lead, Application
from app.modules.compliance.models import ComplianceRequirement, Document, Inspection
from app.modules.workflow.models import JobSchedule, JobExecutionLog, WorkflowDefinition
from app.modules.utilities.models import UtilityReading

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/api/export",
    tags=["Export"],
    dependencies=[Depends(require_permissions(["export", "reports", "portfolio"]))],
)


def _to_dict(obj):
    out = {}
    for c in obj.__table__.columns:
        value = getattr(obj, c.name)
        out[c.name] = str(value) if value is not None else ""
    return out


def _apply_tenant_scope(query, model, user: UserAccount):
    # Role 1 is system admin and should not be tenant-restricted for exports.
    if user.role_id == 1:
        return query
    if user.tenant_org_id and "tenant_org_id" in model.__table__.columns:
        return query.filter(model.tenant_org_id == user.tenant_org_id)
    return query


def _query_rows(
    db: Session,
    user: UserAccount,
    model,
    filter_fn: Optional[Callable] = None,
) -> list[dict]:
    q = db.query(model)
    q = _apply_tenant_scope(q, model, user)
    if filter_fn:
        q = filter_fn(q)
    return [_to_dict(item) for item in q.all()]


def _rows_to_csv(rows: list[dict]) -> io.BytesIO:
    text_buf = io.StringIO()
    if not rows:
        text_buf.write("No data\n")
    else:
        writer = csv.DictWriter(text_buf, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    data = text_buf.getvalue().encode("utf-8")
    out = io.BytesIO(data)
    out.seek(0)
    return out


def _append_sheet(workbook, title: str, rows: list[dict]):
    ws = workbook.create_sheet(title=title[:31] or "Data")
    if not rows:
        ws.append(["No data"])
        return
    headers = list(rows[0].keys())
    ws.append(headers)
    for row in rows:
        ws.append([row.get(key, "") for key in headers])


def _rows_to_excel(sheets: list[tuple[str, list[dict]]]) -> io.BytesIO:
    try:
        from openpyxl import Workbook
    except ModuleNotFoundError as exc:
        raise HTTPException(
            status_code=500,
            detail="Excel export requires openpyxl. Install dependencies from requirements.txt",
        ) from exc

    wb = Workbook()
    # Remove default empty sheet, then create target sheets.
    wb.remove(wb.active)
    for sheet_name, rows in sheets:
        _append_sheet(wb, sheet_name, rows)
    out = io.BytesIO()
    wb.save(out)
    out.seek(0)
    return out


def _stream_file(rows: list[dict], filename_base: str, fmt: str, sheet_name: str) -> StreamingResponse:
    if fmt == "xlsx":
        buf = _rows_to_excel([(sheet_name, rows)])
        return StreamingResponse(
            buf,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename_base}.xlsx"},
        )
    if fmt == "csv":
        buf = _rows_to_csv(rows)
        return StreamingResponse(
            buf,
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename_base}.csv"},
        )
    raise HTTPException(status_code=400, detail="Invalid format. Use csv or xlsx")


@router.get("/properties")
def export_properties(
    format: str = Query("csv", pattern="^(csv|xlsx)$"),
    db: Session = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    rows = _query_rows(db, user, Property, lambda q: q.filter(Property.is_deleted == False))
    return _stream_file(rows, "properties", format, "Properties")


@router.get("/units")
def export_units(
    property_id: Optional[int] = None,
    format: str = Query("csv", pattern="^(csv|xlsx)$"),
    db: Session = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    def _filter(q):
        q = q.filter(Unit.is_deleted == False)
        if property_id:
            q = q.filter(Unit.property_id == property_id)
        return q

    rows = _query_rows(db, user, Unit, _filter)
    return _stream_file(rows, "units", format, "Units")


@router.get("/leases")
def export_leases(
    format: str = Query("csv", pattern="^(csv|xlsx)$"),
    db: Session = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    rows = _query_rows(db, user, Lease)
    return _stream_file(rows, "leases", format, "Leases")


@router.get("/invoices")
def export_invoices(
    status: Optional[str] = None,
    format: str = Query("csv", pattern="^(csv|xlsx)$"),
    db: Session = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    def _filter(q):
        if status:
            q = q.filter(Invoice.invoice_status == status)
        return q

    rows = _query_rows(db, user, Invoice, _filter)
    return _stream_file(rows, "invoices", format, "Invoices")


@router.get("/payments")
def export_payments(
    format: str = Query("csv", pattern="^(csv|xlsx)$"),
    db: Session = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    rows = _query_rows(db, user, Payment)
    return _stream_file(rows, "payments", format, "Payments")


def _page_sheets(page: str, db: Session, user: UserAccount) -> list[tuple[str, list[dict]]]:
    page = page.strip().lower()
    if page in {"dashboard", "reports"}:
        portfolio = {
            "as_of_date": date.today().isoformat(),
            "properties": len(_query_rows(db, user, Property, lambda q: q.filter(Property.is_deleted == False))),
            "units": len(_query_rows(db, user, Unit, lambda q: q.filter(Unit.is_deleted == False))),
            "leases": len(_query_rows(db, user, Lease)),
            "invoices": len(_query_rows(db, user, Invoice)),
            "payments": len(_query_rows(db, user, Payment)),
            "maintenance_requests": len(_query_rows(db, user, MaintenanceRequest)),
        }
        summary_rows = [{"metric": key, "value": value} for key, value in portfolio.items()]
        return [("Summary", summary_rows)]

    if page == "properties":
        return [
            ("Properties", _query_rows(db, user, Property, lambda q: q.filter(Property.is_deleted == False))),
            ("Buildings", _query_rows(db, user, Building, lambda q: q.filter(Building.is_deleted == False))),
            ("Units", _query_rows(db, user, Unit, lambda q: q.filter(Unit.is_deleted == False))),
        ]

    if page == "tenants":
        return [("Tenants", _query_rows(db, user, Tenant, lambda q: q.filter(Tenant.is_deleted == False)))]

    if page == "owners":
        return [("Owners", _query_rows(db, user, Owner, lambda q: q.filter(Owner.is_deleted == False)))]

    if page == "leases":
        return [("Leases", _query_rows(db, user, Lease))]

    if page == "invoices":
        return [
            ("Invoices", _query_rows(db, user, Invoice)),
            ("Payments", _query_rows(db, user, Payment)),
        ]

    if page == "accounting":
        return [
            ("ChartOfAccounts", _query_rows(db, user, ChartOfAccount)),
            ("JournalEntries", _query_rows(db, user, JournalEntry)),
            ("VendorBills", _query_rows(db, user, VendorBill)),
            ("OwnerDistributions", _query_rows(db, user, OwnerDistribution)),
        ]

    if page == "crm":
        return [
            ("Contacts", _query_rows(db, user, Contact)),
            ("Tasks", _query_rows(db, user, Task)),
            ("Threads", _query_rows(db, user, CommunicationThread)),
        ]

    if page == "marketing":
        return [
            ("Listings", _query_rows(db, user, Listing)),
            ("Leads", _query_rows(db, user, Lead)),
            ("Applications", _query_rows(db, user, Application)),
        ]

    if page == "assets":
        return [("Assets", _query_rows(db, user, Asset))]

    if page == "utilities":
        return [("Utilities", _query_rows(db, user, UtilityReading))]

    if page == "maintenance":
        return [
            ("MaintenanceRequests", _query_rows(db, user, MaintenanceRequest)),
            ("WorkOrders", _query_rows(db, user, WorkOrder)),
        ]

    if page == "compliance":
        return [
            ("Requirements", _query_rows(db, user, ComplianceRequirement)),
            ("Documents", _query_rows(db, user, Document)),
            ("Inspections", _query_rows(db, user, Inspection)),
        ]

    if page == "workflow":
        return [
            ("JobSchedules", _query_rows(db, user, JobSchedule)),
            ("JobLogs", _query_rows(db, user, JobExecutionLog)),
            ("WorkflowDefinitions", _query_rows(db, user, WorkflowDefinition)),
        ]

    if page == "settings":
        # Export system-level settings data for admins only.
        if user.role_id != 1:
            raise HTTPException(status_code=403, detail="Admin access required")
        return [("Roles", _query_rows(db, user, Role))]

    if page == "users":
        if user.role_id != 1:
            raise HTTPException(status_code=403, detail="Admin access required")
        return [
            ("Users", _query_rows(db, user, UserAccount)),
            ("Roles", _query_rows(db, user, Role)),
        ]

    if page == "roles":
        if user.role_id != 1:
            raise HTTPException(status_code=403, detail="Admin access required")
        return [("Roles", _query_rows(db, user, Role))]

    # Fallback exports a core portfolio workbook.
    return [
        ("Properties", _query_rows(db, user, Property, lambda q: q.filter(Property.is_deleted == False))),
        ("Units", _query_rows(db, user, Unit, lambda q: q.filter(Unit.is_deleted == False))),
        ("Leases", _query_rows(db, user, Lease)),
        ("Invoices", _query_rows(db, user, Invoice)),
        ("Payments", _query_rows(db, user, Payment)),
    ]


@router.get("/excel")
def export_screen_excel(
    page: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    sheets = _page_sheets(page, db, user)
    if not sheets:
        raise HTTPException(status_code=404, detail="No export data available")
    buf = _rows_to_excel(sheets)
    safe_page = "".join(ch for ch in page.lower() if ch.isalnum() or ch in {"-", "_"}).strip("-_") or "export"
    filename = f"{safe_page}_{date.today().isoformat()}.xlsx"
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
