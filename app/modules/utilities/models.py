"""Utilities module models."""
from sqlalchemy import Column, Integer, String, Text, Numeric, Date, DateTime, ForeignKey, func
from app.database import Base


class UtilityReading(Base):
    __tablename__ = "utility_readings"
    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_org_id = Column(Integer, ForeignKey("tenant_orgs.id"))
    property_id = Column(Integer, ForeignKey("properties.id"), nullable=True)
    unit_id = Column(Integer, ForeignKey("units.id"), nullable=True)
    utility_type = Column(String(50), nullable=False)  # Electricity, Water, Gas, Internet, Sewage
    meter_number = Column(String(100))
    reading_date = Column(Date, nullable=False)
    previous_reading = Column(Numeric(12, 2), default=0)
    current_reading = Column(Numeric(12, 2), default=0)
    usage = Column(Numeric(12, 2), default=0)
    rate_per_unit = Column(Numeric(10, 4), default=0)
    total_cost = Column(Numeric(12, 2), default=0)
    billing_period_start = Column(Date)
    billing_period_end = Column(Date)
    status = Column(String(20), default="Pending")  # Pending, Billed, Paid
    invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=True)
    notes = Column(Text)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
