"""Pydantic schemas for the Leasing module."""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import date


class LeaseCreate(BaseModel):
    lease_number: str = Field(..., min_length=1)
    property_id: int
    tenant_id: int
    start_date: date
    end_date: date
    base_rent_amount: float = Field(..., gt=0)
    base_rent_currency: str = Field(default="USD")
    rent_frequency: str = Field(default="Monthly")
    unit_id: Optional[int] = None
    owner_id: Optional[int] = None
    lease_type: Optional[str] = Field(default="Fixed")
    notice_period_days: Optional[int] = None
    discounts: Optional[float] = None
    service_charge_percent: Optional[float] = None
    revenue_share_percent: Optional[float] = None
    possession_date: Optional[date] = None

class LeaseUpdate(BaseModel):
    lease_status: Optional[str] = None
    base_rent_amount: Optional[float] = None
    end_date: Optional[date] = None
    notice_period_days: Optional[int] = None
    termination_date: Optional[date] = None
    termination_reason: Optional[str] = None

class SecurityDepositCreate(BaseModel):
    lease_id: int
    deposit_type: str = Field(default="Security")
    amount: float = Field(..., gt=0)
    currency: str = Field(default="USD")
    received_date: Optional[date] = None
    bank_reference: Optional[str] = None
