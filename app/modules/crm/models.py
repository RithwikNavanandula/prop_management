"""CRM models – Contact, CommunicationThread, Message, NotificationTemplate, NotificationLog, Task."""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, JSON
from sqlalchemy.sql import func
from app.database import Base


class Contact(Base):
    __tablename__ = "contacts"
    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_org_id = Column(Integer, ForeignKey("tenant_orgs.id"))
    contact_type = Column(String(30))
    first_name = Column(String(100))
    last_name = Column(String(100))
    email = Column(String(255))
    phone = Column(String(50))
    preferred_channel = Column(String(20), default="Email")
    status = Column(String(20), default="Active")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class CommunicationThread(Base):
    __tablename__ = "communication_threads"
    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_org_id = Column(Integer, ForeignKey("tenant_orgs.id"))
    thread_type = Column(String(30))
    related_entity_type = Column(String(50))
    related_entity_id = Column(Integer)
    subject = Column(String(300))
    status = Column(String(20), default="Open")
    created_at = Column(DateTime, server_default=func.now())
    closed_at = Column(DateTime)


class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True, autoincrement=True)
    thread_id = Column(Integer, ForeignKey("communication_threads.id"), nullable=False)
    sender_type = Column(String(30))
    sender_id = Column(Integer)
    recipient_type = Column(String(30))
    recipient_id = Column(Integer)
    channel = Column(String(20), default="InApp")
    subject = Column(String(300))
    body = Column(Text)
    sent_at = Column(DateTime, server_default=func.now())
    read_at = Column(DateTime)
    has_attachment = Column(Boolean, default=False)


class NotificationTemplate(Base):
    __tablename__ = "notification_templates"
    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_org_id = Column(Integer, ForeignKey("tenant_orgs.id"))
    template_name = Column(String(200), nullable=False)
    channel = Column(String(20), default="Email")
    subject = Column(String(300))
    body_template = Column(Text)
    variables = Column(JSON)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())


class NotificationLog(Base):
    __tablename__ = "notification_logs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    template_id = Column(Integer, ForeignKey("notification_templates.id"))
    recipient_type = Column(String(30))
    recipient_id = Column(Integer)
    channel = Column(String(20))
    subject = Column(String(300))
    body = Column(Text)
    sent_at = Column(DateTime, server_default=func.now())
    delivery_status = Column(String(20), default="Sent")
    error_message = Column(Text)


class Task(Base):
    __tablename__ = "tasks"
    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_org_id = Column(Integer, ForeignKey("tenant_orgs.id"))
    title = Column(String(300), nullable=False)
    description = Column(Text)
    assigned_to = Column(Integer, ForeignKey("user_accounts.id"))
    due_date = Column(DateTime)
    priority = Column(String(10), default="Medium")
    status = Column(String(20), default="Open")
    related_entity_type = Column(String(50))
    related_entity_id = Column(Integer)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
