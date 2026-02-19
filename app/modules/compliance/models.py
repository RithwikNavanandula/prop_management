"""Compliance models – Document, DocumentType, ComplianceRequirement, ComplianceItem, Inspection."""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Date, ForeignKey, Text
from sqlalchemy.sql import func
from app.database import Base


class DocumentType(Base):
    __tablename__ = "document_types"
    id = Column(Integer, primary_key=True, autoincrement=True)
    type_name = Column(String(100), nullable=False)
    category = Column(String(50))
    is_required = Column(Boolean, default=False)
    retention_days = Column(Integer)
    created_at = Column(DateTime, server_default=func.now())


class Document(Base):
    __tablename__ = "documents"
    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_org_id = Column(Integer, ForeignKey("tenant_orgs.id"))
    owner_entity_type = Column(String(50), nullable=False)
    owner_entity_id = Column(Integer, nullable=False)
    document_type_id = Column(Integer, ForeignKey("document_types.id"))
    file_name = Column(String(300))
    file_path = Column(String(500))
    mime_type = Column(String(100))
    upload_date = Column(DateTime, server_default=func.now())
    expiry_date = Column(Date)
    is_signed = Column(Boolean, default=False)
    esign_envelope_id = Column(String(200))
    version_number = Column(Integer, default=1)
    created_at = Column(DateTime, server_default=func.now())


class ComplianceRequirement(Base):
    __tablename__ = "compliance_requirements"
    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_org_id = Column(Integer, ForeignKey("tenant_orgs.id"))
    requirement_name = Column(String(200), nullable=False)
    entity_type = Column(String(50))
    document_type_id = Column(Integer, ForeignKey("document_types.id"))
    frequency = Column(String(30))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())


class ComplianceItem(Base):
    __tablename__ = "compliance_items"
    id = Column(Integer, primary_key=True, autoincrement=True)
    requirement_id = Column(Integer, ForeignKey("compliance_requirements.id"), nullable=False)
    entity_type = Column(String(50))
    entity_id = Column(Integer)
    due_date = Column(Date)
    status = Column(String(20), default="Pending")
    escalation_level = Column(Integer, default=0)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class Inspection(Base):
    __tablename__ = "inspections"
    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_org_id = Column(Integer, ForeignKey("tenant_orgs.id"))
    property_id = Column(Integer, ForeignKey("properties.id"))
    unit_id = Column(Integer, ForeignKey("units.id"))
    inspection_type = Column(String(30), default="Routine")
    inspector_id = Column(Integer)
    scheduled_date = Column(Date)
    completed_date = Column(Date)
    overall_condition = Column(String(30))
    notes = Column(Text)
    status = Column(String(20), default="Scheduled")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class DocumentVersion(Base):
    __tablename__ = "document_versions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_org_id = Column(Integer, ForeignKey("tenant_orgs.id"))
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    version_number = Column(Integer, nullable=False)
    file_name = Column(String(300))
    file_path = Column(String(500))
    mime_type = Column(String(100))
    checksum = Column(String(128))
    notes = Column(Text)
    uploaded_by = Column(Integer)
    uploaded_at = Column(DateTime, server_default=func.now())


class DocumentObligation(Base):
    __tablename__ = "document_obligations"
    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_org_id = Column(Integer, ForeignKey("tenant_orgs.id"))
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    obligation_type = Column(String(50), nullable=False)  # Expiry/Renewal/Regulatory
    due_date = Column(Date, nullable=False)
    status = Column(String(20), default="Open")  # Open/Completed/Waived/Overdue
    assigned_to = Column(Integer)
    notes = Column(Text)
    completed_by = Column(Integer)
    completed_at = Column(DateTime)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
