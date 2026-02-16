"""Maintenance models – Request, WorkOrder, SLA, Cost, Attachment."""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Date, Numeric, ForeignKey, Text
from sqlalchemy.sql import func
from app.database import Base


class MaintenanceSLA(Base):
    __tablename__ = "maintenance_slas"
    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_org_id = Column(Integer, ForeignKey("tenant_orgs.id"))
    sla_name = Column(String(200), nullable=False)
    category = Column(String(50))
    priority = Column(String(10))
    target_response_min = Column(Integer, default=60)
    target_resolution_min = Column(Integer, default=1440)
    escalation_rules = Column(Text)
    status = Column(String(20), default="Active")
    created_at = Column(DateTime, server_default=func.now())


class MaintenanceRequest(Base):
    __tablename__ = "maintenance_requests"
    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_org_id = Column(Integer, ForeignKey("tenant_orgs.id"))
    request_number = Column(String(50), nullable=False, unique=True, index=True)
    property_id = Column(Integer, ForeignKey("properties.id"), nullable=False)
    unit_id = Column(Integer, ForeignKey("units.id"))
    tenant_id = Column(Integer, ForeignKey("tenants.id"))
    reported_by = Column(String(200))
    channel = Column(String(30), default="Portal")
    description = Column(Text, nullable=False)
    category = Column(String(50), default="General")
    priority = Column(String(10), default="P3")
    status = Column(String(30), default="New")
    reported_at = Column(DateTime, server_default=func.now())
    first_response_at = Column(DateTime)
    completed_at = Column(DateTime)
    sla_target_response_min = Column(Integer)
    sla_target_resolution_min = Column(Integer)
    sla_response_breached = Column(Boolean, default=False)
    sla_resolution_breached = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class WorkOrder(Base):
    __tablename__ = "work_orders"
    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_org_id = Column(Integer, ForeignKey("tenant_orgs.id"))
    work_order_number = Column(String(50), nullable=False, unique=True, index=True)
    request_id = Column(Integer, ForeignKey("maintenance_requests.id"))
    property_id = Column(Integer, ForeignKey("properties.id"), nullable=False)
    unit_id = Column(Integer, ForeignKey("units.id"))
    assigned_vendor_id = Column(Integer, ForeignKey("vendors.id"))
    assigned_staff_id = Column(Integer, ForeignKey("staff_users.id"))
    scheduled_start = Column(DateTime)
    scheduled_end = Column(DateTime)
    actual_start = Column(DateTime)
    actual_end = Column(DateTime)
    status = Column(String(30), default="Open")
    access_instructions = Column(Text)
    estimated_cost = Column(Numeric(14, 2))
    actual_cost = Column(Numeric(14, 2))
    currency = Column(String(10), default="USD")
    labor_cost = Column(Numeric(14, 2), default=0)
    material_cost = Column(Numeric(14, 2), default=0)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class WorkOrderTask(Base):
    __tablename__ = "work_order_tasks"
    id = Column(Integer, primary_key=True, autoincrement=True)
    work_order_id = Column(Integer, ForeignKey("work_orders.id"), nullable=False)
    task_description = Column(String(500), nullable=False)
    status = Column(String(20), default="Pending")
    assigned_to = Column(String(200))
    estimated_hours = Column(Numeric(6, 2))
    actual_hours = Column(Numeric(6, 2))
    created_at = Column(DateTime, server_default=func.now())


class WorkOrderAssignment(Base):
    __tablename__ = "work_order_assignments"
    id = Column(Integer, primary_key=True, autoincrement=True)
    work_order_id = Column(Integer, ForeignKey("work_orders.id"), nullable=False)
    assignee_type = Column(String(20), nullable=False)
    assignee_id = Column(Integer, nullable=False)
    assigned_at = Column(DateTime, server_default=func.now())
    completed_at = Column(DateTime)


class MaintenanceCost(Base):
    __tablename__ = "maintenance_costs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    work_order_id = Column(Integer, ForeignKey("work_orders.id"), nullable=False)
    cost_type = Column(String(30), nullable=False)
    description = Column(String(500))
    amount = Column(Numeric(14, 2), nullable=False)
    currency = Column(String(10), default="USD")
    vendor_id = Column(Integer, ForeignKey("vendors.id"))
    created_at = Column(DateTime, server_default=func.now())


class MaintenanceAttachment(Base):
    __tablename__ = "maintenance_attachments"
    id = Column(Integer, primary_key=True, autoincrement=True)
    request_id = Column(Integer, ForeignKey("maintenance_requests.id"))
    work_order_id = Column(Integer, ForeignKey("work_orders.id"))
    file_name = Column(String(300))
    file_path = Column(String(500))
    mime_type = Column(String(100))
    uploaded_by = Column(Integer)
    uploaded_at = Column(DateTime, server_default=func.now())


class WorkOrderTimeEntry(Base):
    __tablename__ = "work_order_time_entries"
    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_org_id = Column(Integer, ForeignKey("tenant_orgs.id"))
    work_order_id = Column(Integer, ForeignKey("work_orders.id"), nullable=False)
    vendor_id = Column(Integer, ForeignKey("vendors.id"))
    staff_id = Column(Integer, ForeignKey("staff_users.id"))
    start_time = Column(DateTime)
    end_time = Column(DateTime)
    hours = Column(Numeric(6, 2), default=0)
    notes = Column(Text)
    created_at = Column(DateTime, server_default=func.now())
