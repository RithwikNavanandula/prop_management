"""Auth models – UserAccount, Role, AuditLog."""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, JSON
from sqlalchemy.sql import func
from app.database import Base


class Role(Base):
    __tablename__ = "roles"
    id = Column(Integer, primary_key=True, autoincrement=True)
    role_name = Column(String(50), unique=True, nullable=False)
    description = Column(String(255))
    permissions = Column(JSON)
    is_system = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class UserAccount(Base):
    __tablename__ = "user_accounts"
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(200))
    role_id = Column(Integer, ForeignKey("roles.id"), nullable=False)
    tenant_org_id = Column(Integer, ForeignKey("tenant_orgs.id"), nullable=True)
    linked_entity_type = Column(String(50))  # Staff/Tenant/Owner/Vendor
    linked_entity_id = Column(Integer)
    is_active = Column(Boolean, default=True)
    last_login_at = Column(DateTime)
    mfa_enabled = Column(Boolean, default=False)
    avatar_url = Column(String(500))
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("user_accounts.id"))
    action = Column(String(50), nullable=False)
    entity_type = Column(String(100))
    entity_id = Column(Integer)
    old_values = Column(JSON)
    new_values = Column(JSON)
    ip_address = Column(String(45))
    timestamp = Column(DateTime, server_default=func.now())
