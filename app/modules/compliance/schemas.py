"""Pydantic schemas for the Compliance module."""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import date


class RequirementCreate(BaseModel):
    name: str = Field(..., min_length=1)
    entity_type: Optional[str] = None
    description: Optional[str] = None
    frequency: Optional[str] = None
    due_date: Optional[date] = None
    status: str = Field(default="Pending")

class RequirementUpdate(BaseModel):
    name: Optional[str] = None
    status: Optional[str] = None
    due_date: Optional[date] = None

class InspectionCreate(BaseModel):
    property_id: int
    unit_id: Optional[int] = None
    inspection_type: Optional[str] = None
    scheduled_date: Optional[date] = None
    inspector_name: Optional[str] = None
    status: str = Field(default="Scheduled")

class DocumentTypeCreate(BaseModel):
    name: str = Field(..., min_length=1)
    category: Optional[str] = None
    required: bool = False
    expiry_months: Optional[int] = None
