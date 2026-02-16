"""Pydantic schemas for the Maintenance module."""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import date


class RequestCreate(BaseModel):
    property_id: int
    unit_id: Optional[int] = None
    tenant_id: Optional[int] = None
    category: Optional[str] = None
    priority: str = Field(default="Medium")
    title: str = Field(..., min_length=1)
    description: Optional[str] = None

class RequestUpdate(BaseModel):
    status: Optional[str] = None
    priority: Optional[str] = None
    category: Optional[str] = None
    assigned_to: Optional[int] = None
    resolution_notes: Optional[str] = None

class WorkOrderCreate(BaseModel):
    request_id: int
    assigned_vendor_id: Optional[int] = None
    title: Optional[str] = None
    description: Optional[str] = None
    priority: str = Field(default="Medium")
    scheduled_date: Optional[date] = None
    estimated_cost: Optional[float] = None

class WorkOrderUpdate(BaseModel):
    status: Optional[str] = None
    assigned_vendor_id: Optional[int] = None
    actual_cost: Optional[float] = None
    completion_date: Optional[date] = None
    notes: Optional[str] = None

class SLARuleCreate(BaseModel):
    name: str
    priority: str
    response_hours: int
    resolution_hours: int
    escalation_hours: Optional[int] = None
