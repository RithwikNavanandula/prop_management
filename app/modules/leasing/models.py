"""Leasing models – Lease, LeaseUnitLink, LeasePartyLink, RentSchedule, SecurityDeposit, etc."""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Date, Text, Float, Numeric, ForeignKey, JSON
from sqlalchemy.sql import func
from app.database import Base


class Lease(Base):
    __tablename__ = "leases"
    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_org_id = Column(Integer, ForeignKey("tenant_orgs.id"))
    lease_number = Column(String(50), nullable=False, unique=True, index=True)
    lease_type = Column(String(30), default="Residential")
    lease_status = Column(String(30), default="Draft")
    property_id = Column(Integer, ForeignKey("properties.id"), nullable=False)
    unit_id = Column(Integer, ForeignKey("units.id"))
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    owner_id = Column(Integer, ForeignKey("owners.id"))
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    possession_date = Column(Date)
    notice_period_days = Column(Integer, default=30)
    termination_date = Column(Date)
    termination_reason = Column(String(300))
    base_rent_amount = Column(Numeric(14, 2), nullable=False)
    base_rent_currency = Column(String(10), default="USD")
    rent_frequency = Column(String(20), default="Monthly")
    payment_terms = Column(String(200))
    late_fee_rule_id = Column(Integer, ForeignKey("late_fee_rules.id"))
    discounts = Column(Numeric(14, 2), default=0)
    rent_type = Column(String(30), default="Fixed")
    revenue_share_percent = Column(Numeric(5, 2))
    cam_charge_basis = Column(String(30))
    service_charge_percent = Column(Numeric(5, 2))
    indexation_type = Column(String(30))
    indexation_frequency = Column(String(20))
    next_indexation_date = Column(Date)
    notes = Column(Text)
    is_deleted = Column(Boolean, default=False)
    created_by = Column(Integer)
    created_at = Column(DateTime, server_default=func.now())
    updated_by = Column(Integer)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class LeaseUnitLink(Base):
    __tablename__ = "lease_unit_links"
    id = Column(Integer, primary_key=True, autoincrement=True)
    lease_id = Column(Integer, ForeignKey("leases.id"), nullable=False)
    unit_id = Column(Integer, ForeignKey("units.id"), nullable=False)
    allocated_rent = Column(Numeric(14, 2))
    created_at = Column(DateTime, server_default=func.now())


class LeasePartyLink(Base):
    __tablename__ = "lease_party_links"
    id = Column(Integer, primary_key=True, autoincrement=True)
    lease_id = Column(Integer, ForeignKey("leases.id"), nullable=False)
    party_type = Column(String(30), nullable=False)
    party_id = Column(Integer, nullable=False)
    created_at = Column(DateTime, server_default=func.now())


class RentSchedule(Base):
    __tablename__ = "rent_schedules"
    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_org_id = Column(Integer, ForeignKey("tenant_orgs.id"))
    lease_id = Column(Integer, ForeignKey("leases.id"), nullable=False)
    due_date = Column(Date, nullable=False)
    period_start = Column(Date)
    period_end = Column(Date)
    scheduled_amount = Column(Numeric(14, 2), nullable=False)
    currency = Column(String(10), default="USD")
    tax_amount = Column(Numeric(14, 2), default=0)
    total_amount = Column(Numeric(14, 2))
    is_prorated = Column(Boolean, default=False)
    indexation_applied = Column(Boolean, default=False)
    is_paid = Column(Boolean, default=False)
    paid_date = Column(Date)
    outstanding_amount = Column(Numeric(14, 2))
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class SecurityDeposit(Base):
    __tablename__ = "security_deposits"
    id = Column(Integer, primary_key=True, autoincrement=True)
    lease_id = Column(Integer, ForeignKey("leases.id"), nullable=False)
    deposit_type = Column(String(30), default="Cash")
    deposit_amount = Column(Numeric(14, 2), nullable=False)
    currency = Column(String(10), default="USD")
    held_in_account = Column(String(200))
    received_date = Column(Date)
    refunded_date = Column(Date)
    refund_amount = Column(Numeric(14, 2))
    refund_reason = Column(String(300))
    status = Column(String(20), default="Held")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class LeaseIndexationRule(Base):
    __tablename__ = "lease_indexation_rules"
    id = Column(Integer, primary_key=True, autoincrement=True)
    lease_id = Column(Integer, ForeignKey("leases.id"), nullable=False)
    index_type = Column(String(30), default="Fixed")
    percentage_or_index = Column(Numeric(5, 2))
    frequency = Column(String(20), default="Yearly")
    next_application_date = Column(Date)
    created_at = Column(DateTime, server_default=func.now())


class LeaseDocument(Base):
    __tablename__ = "lease_documents"
    id = Column(Integer, primary_key=True, autoincrement=True)
    lease_id = Column(Integer, ForeignKey("leases.id"), nullable=False)
    document_type_id = Column(Integer)
    file_name = Column(String(300))
    file_path = Column(String(500))
    upload_date = Column(DateTime, server_default=func.now())
    is_signed = Column(Boolean, default=False)
    esign_envelope_id = Column(String(200))
    version_number = Column(Integer, default=1)
    created_at = Column(DateTime, server_default=func.now())
