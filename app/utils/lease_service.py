"""Lease renewal workflow – detection, offer, auto-terminate."""
import logging
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.modules.leasing.models import Lease, RentSchedule

logger = logging.getLogger(__name__)


def detect_expiring_leases(days_ahead: int = 60):
    """Find leases expiring within X days that haven't been renewed."""
    db = SessionLocal()
    try:
        cutoff = date.today() + timedelta(days=days_ahead)
        leases = db.query(Lease).filter(
            Lease.end_date <= cutoff,
            Lease.end_date >= date.today(),
            Lease.lease_status == "Active"
        ).all()
        return [{"lease_id": l.id, "lease_number": l.lease_number,
                 "end_date": str(l.end_date), "tenant_id": l.tenant_id,
                 "days_remaining": (l.end_date - date.today()).days}
                for l in leases]
    finally:
        db.close()


def renew_lease(lease_id: int, new_end_date: date = None, new_rent: float = None, escalation_pct: float = None):
    """Renew a lease — extend end date and optionally adjust rent."""
    db = SessionLocal()
    try:
        lease = db.query(Lease).filter(Lease.id == lease_id).first()
        if not lease:
            return {"error": "Lease not found"}
        if lease.lease_status != "Active":
            return {"error": "Only Active leases can be renewed"}

        old_end = lease.end_date
        if not new_end_date:
            new_end_date = old_end + relativedelta(years=1)

        if escalation_pct and not new_rent:
            new_rent = float(lease.base_rent_amount or 0) * (1 + escalation_pct / 100)
        elif not new_rent:
            new_rent = float(lease.base_rent_amount or 0)

        lease.end_date = new_end_date
        lease.base_rent_amount = new_rent
        lease.lease_status = "Renewed"

        # Generate new rent schedules for renewal period
        freq = lease.rent_frequency or "Monthly"
        current = old_end + timedelta(days=1)  # start after previous end
        while current <= new_end_date:
            sched = RentSchedule(
                lease_id=lease.id, tenant_org_id=lease.tenant_org_id,
                due_date=current, amount_due=new_rent,
                currency=lease.base_rent_currency or "USD", status="Scheduled"
            )
            db.add(sched)
            if freq == "Monthly":
                current += relativedelta(months=1)
            elif freq == "Quarterly":
                current += relativedelta(months=3)
            elif freq == "Yearly":
                current += relativedelta(years=1)
            else:
                current += relativedelta(months=1)

        db.commit()
        logger.info("Lease %s renewed until %s, rent = %s", lease.lease_number, new_end_date, new_rent)
        return {"lease_id": lease_id, "new_end_date": str(new_end_date), "new_rent": new_rent}
    except Exception as e:
        db.rollback()
        logger.error("Lease renewal error: %s", e)
        return {"error": str(e)}
    finally:
        db.close()


def auto_terminate_expired():
    """Terminate leases that have expired and were not renewed."""
    db = SessionLocal()
    try:
        expired = db.query(Lease).filter(
            Lease.end_date < date.today(),
            Lease.lease_status == "Active"
        ).all()
        count = 0
        for lease in expired:
            lease.lease_status = "Expired"
            lease.termination_date = date.today()
            lease.termination_reason = "Auto-terminated: lease expired"
            count += 1
        db.commit()
        logger.info("Auto-terminated %d expired leases", count)
        return count
    except Exception as e:
        db.rollback()
        logger.error("Auto-terminate error: %s", e)
        return 0
    finally:
        db.close()
