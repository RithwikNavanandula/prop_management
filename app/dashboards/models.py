"""Dashboard mart models."""
from sqlalchemy import Column, Integer, String, Date, DateTime, Numeric, ForeignKey, JSON
from sqlalchemy.sql import func
from app.database import Base


class KPIDailyFact(Base):
    __tablename__ = "kpi_daily_facts"
    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_org_id = Column(Integer, ForeignKey("tenant_orgs.id"), nullable=False)
    fact_date = Column(Date, nullable=False, index=True)
    scope_type = Column(String(30), default="Tenant")  # Tenant/Region/Property
    scope_id = Column(Integer)
    metric_code = Column(String(100), nullable=False, index=True)
    metric_value = Column(Numeric(18, 4), nullable=False, default=0)
    currency = Column(String(10))
    dimensions = Column(JSON)
    created_at = Column(DateTime, server_default=func.now())
