"""Email notification hooks for property management events."""
import logging
from datetime import date, timedelta
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.modules.leasing.models import Lease
from app.modules.billing.models import Invoice
from app.modules.maintenance.models import MaintenanceRequest
from app.modules.properties.models import Tenant
from app.utils.email_service import send_email

logger = logging.getLogger(__name__)


async def notify_lease_expiry(days_ahead: int = 60):
    """Send email notifications for leases expiring within X days."""
    db = SessionLocal()
    try:
        cutoff = date.today() + timedelta(days=days_ahead)
        leases = db.query(Lease).filter(
            Lease.end_date <= cutoff,
            Lease.end_date >= date.today(),
            Lease.lease_status == "Active"
        ).all()

        for lease in leases:
            tenant = db.query(Tenant).filter(Tenant.id == lease.tenant_id).first()
            if not tenant or not tenant.email:
                continue
            days_left = (lease.end_date - date.today()).days
            try:
                await send_email(
                    subject=f"Lease Expiring in {days_left} Days – {lease.lease_number}",
                    recipient=tenant.email,
                    html_content=f"""
                    <h2>Lease Expiry Notice</h2>
                    <p>Your lease <strong>{lease.lease_number}</strong> expires on
                    <strong>{lease.end_date}</strong> ({days_left} days remaining).</p>
                    <p>Please contact management to discuss renewal options.</p>
                    """
                )
                logger.info("Lease expiry email sent to %s for lease %s", tenant.email, lease.lease_number)
            except Exception as e:
                logger.error("Failed to send lease expiry email: %s", e)
    finally:
        db.close()


async def notify_overdue_invoices():
    """Send email for overdue invoices."""
    db = SessionLocal()
    try:
        overdue = db.query(Invoice).filter(
            Invoice.due_date < date.today(),
            Invoice.invoice_status.in_(["Posted", "PartiallyPaid"])
        ).all()

        for inv in overdue:
            tenant = db.query(Tenant).filter(Tenant.id == inv.tenant_id).first()
            if not tenant or not tenant.email:
                continue
            days_overdue = (date.today() - inv.due_date).days
            try:
                await send_email(
                    subject=f"Overdue Invoice – {inv.invoice_number}",
                    recipient=tenant.email,
                    html_content=f"""
                    <h2>Payment Overdue</h2>
                    <p>Invoice <strong>{inv.invoice_number}</strong> for
                    <strong>{inv.currency} {inv.total_amount}</strong> was due on
                    <strong>{inv.due_date}</strong> ({days_overdue} days overdue).</p>
                    <p>Please make payment at your earliest convenience.</p>
                    """
                )
            except Exception as e:
                logger.error("Failed to send overdue email: %s", e)
    finally:
        db.close()


async def notify_maintenance_update(request_id: int, status: str):
    """Send email when maintenance request status changes."""
    db = SessionLocal()
    try:
        req = db.query(MaintenanceRequest).filter(MaintenanceRequest.id == request_id).first()
        if not req or not req.tenant_id:
            return
        tenant = db.query(Tenant).filter(Tenant.id == req.tenant_id).first()
        if not tenant or not tenant.email:
            return
        try:
            await send_email(
                subject=f"Maintenance Update – Request #{request_id}",
                recipient=tenant.email,
                html_content=f"""
                <h2>Maintenance Request Update</h2>
                <p>Your request <strong>#{request_id}</strong> – <em>{req.title}</em>
                has been updated to: <strong>{status}</strong>.</p>
                """
            )
        except Exception as e:
            logger.error("Failed to send maintenance email: %s", e)
    finally:
        db.close()
