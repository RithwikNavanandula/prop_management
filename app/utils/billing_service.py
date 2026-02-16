"""Automated billing – rent invoice generation + late fee application."""
import logging
from datetime import date, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database import SessionLocal
from app.modules.leasing.models import Lease, RentSchedule
from app.modules.billing.models import Invoice, InvoiceLine, LateFeeRule

logger = logging.getLogger(__name__)


def generate_invoices_for_today():
    """Generate invoices from rent schedules due today that haven't been billed yet."""
    db = SessionLocal()
    try:
        today = date.today()
        schedules = db.query(RentSchedule).filter(
            RentSchedule.due_date == today,
            RentSchedule.status.in_(["Scheduled", "Pending"])
        ).all()

        created = 0
        for sched in schedules:
            lease = db.query(Lease).filter(Lease.id == sched.lease_id).first()
            if not lease or lease.lease_status not in ("Active", "Renewed"):
                continue

            # Check if invoice already exists for this schedule
            existing = db.query(Invoice).filter(
                Invoice.lease_id == lease.id,
                Invoice.due_date == sched.due_date
            ).first()
            if existing:
                continue

            inv = Invoice(
                tenant_org_id=lease.tenant_org_id,
                tenant_id=lease.tenant_id,
                property_id=lease.property_id,
                lease_id=lease.id,
                invoice_number=f"INV-{lease.lease_number}-{today.strftime('%Y%m%d')}",
                invoice_date=today,
                due_date=sched.due_date,
                total_amount=float(sched.amount_due or 0),
                currency=lease.base_rent_currency or "USD",
                invoice_status="Posted"
            )
            db.add(inv)
            db.flush()

            line = InvoiceLine(
                invoice_id=inv.id,
                description=f"Rent – {sched.due_date.strftime('%B %Y')}",
                quantity=1,
                unit_price=float(sched.amount_due or 0),
                line_total=float(sched.amount_due or 0)
            )
            db.add(line)
            sched.status = "Invoiced"
            created += 1

        db.commit()
        logger.info("Auto-billing: created %d invoices", created)
        return created
    except Exception as e:
        db.rollback()
        logger.error("Auto-billing error: %s", e)
        return 0
    finally:
        db.close()


def apply_late_fees():
    """Apply late fees to overdue invoices based on rules."""
    db = SessionLocal()
    try:
        today = date.today()
        rules = db.query(LateFeeRule).filter(LateFeeRule.is_active == True).all()
        applied = 0

        for rule in rules:
            grace_days = rule.grace_period_days or 5
            cutoff = today - timedelta(days=grace_days)

            overdue = db.query(Invoice).filter(
                Invoice.due_date <= cutoff,
                Invoice.invoice_status.in_(["Posted", "PartiallyPaid"]),
                Invoice.tenant_org_id == rule.tenant_org_id
            ).all()

            for inv in overdue:
                # Check if late fee already applied
                existing_fee = db.query(InvoiceLine).filter(
                    InvoiceLine.invoice_id == inv.id,
                    InvoiceLine.description.like("%Late Fee%")
                ).first()
                if existing_fee:
                    continue

                if rule.fee_type == "Flat":
                    fee = float(rule.flat_fee or 0)
                elif rule.fee_type == "Percentage":
                    fee = float(inv.total_amount or 0) * float(rule.percentage or 0) / 100
                else:
                    continue

                if rule.max_fee and fee > float(rule.max_fee):
                    fee = float(rule.max_fee)

                if fee > 0:
                    line = InvoiceLine(
                        invoice_id=inv.id,
                        description=f"Late Fee ({rule.rule_name})",
                        quantity=1,
                        unit_price=fee,
                        line_total=fee
                    )
                    db.add(line)
                    inv.total_amount = float(inv.total_amount or 0) + fee
                    applied += 1

        db.commit()
        logger.info("Late fees: applied %d fees", applied)
        return applied
    except Exception as e:
        db.rollback()
        logger.error("Late fee error: %s", e)
        return 0
    finally:
        db.close()
