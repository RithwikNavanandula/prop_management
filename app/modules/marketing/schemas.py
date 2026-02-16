"""Pydantic schemas for the Marketing module."""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import date


class ListingCreate(BaseModel):
    unit_id: int
    title: str = Field(..., min_length=1)
    description: Optional[str] = None
    asking_rent: Optional[float] = None
    status: str = Field(default="Active")
    available_from: Optional[date] = None

class LeadCreate(BaseModel):
    first_name: str = Field(..., min_length=1)
    last_name: str = Field(..., min_length=1)
    email: Optional[str] = None
    phone: Optional[str] = None
    source: Optional[str] = None
    listing_id: Optional[int] = None
    status: str = Field(default="New")

class LeadUpdate(BaseModel):
    status: Optional[str] = None
    notes: Optional[str] = None
    assigned_to: Optional[int] = None

class ApplicationCreate(BaseModel):
    lead_id: Optional[int] = None
    unit_id: int
    applicant_name: str = Field(..., min_length=1)
    applicant_email: Optional[str] = None
    applicant_phone: Optional[str] = None
    desired_move_in: Optional[date] = None
    status: str = Field(default="Submitted")
