"""Pydantic schemas for the CRM module."""
from pydantic import BaseModel, Field
from typing import Optional


class ContactCreate(BaseModel):
    first_name: str = Field(..., min_length=1)
    last_name: str = Field(..., min_length=1)
    email: Optional[str] = None
    phone: Optional[str] = None
    contact_type: Optional[str] = None
    company: Optional[str] = None

class ThreadCreate(BaseModel):
    subject: str = Field(..., min_length=1)
    contact_id: Optional[int] = None
    channel: Optional[str] = Field(default="Email")
    status: str = Field(default="Open")

class MessageCreate(BaseModel):
    thread_id: int
    body: str = Field(..., min_length=1)
    direction: str = Field(default="Outbound")

class TaskCreate(BaseModel):
    title: str = Field(..., min_length=1)
    description: Optional[str] = None
    assigned_to: Optional[int] = None
    due_date: Optional[str] = None
    priority: str = Field(default="Medium")
    status: str = Field(default="Open")
    related_entity_type: Optional[str] = None
    related_entity_id: Optional[int] = None
