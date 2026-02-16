"""Pydantic schemas for the Billing module."""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date


class InvoiceLineCreate(BaseModel):
    description: str
    quantity: float = Field(default=1)
    unit_price: float
    line_total: Optional[float] = None
    account_id: Optional[int] = None

class InvoiceCreate(BaseModel):
    invoice_number: str = Field(..., min_length=1)
    tenant_id: int
    property_id: Optional[int] = None
    unit_id: Optional[int] = None
    lease_id: Optional[int] = None
    invoice_date: Optional[date] = None
    due_date: date
    total_amount: float = Field(..., gt=0)
    currency: str = Field(default="USD")
    invoice_status: str = Field(default="Draft")
    lines: List[InvoiceLineCreate] = []

class InvoiceUpdate(BaseModel):
    invoice_status: Optional[str] = None
    due_date: Optional[date] = None
    total_amount: Optional[float] = None

class PaymentAllocationCreate(BaseModel):
    invoice_id: int
    amount: float = Field(..., gt=0)

class PaymentCreate(BaseModel):
    tenant_id: int
    amount: float = Field(..., gt=0)
    currency: str = Field(default="USD")
    payment_date: Optional[date] = None
    payment_method: Optional[str] = None
    reference_number: Optional[str] = None
    allocations: List[PaymentAllocationCreate] = []

class LateFeeRuleCreate(BaseModel):
    name: str
    fee_type: str = Field(default="Flat")
    fee_amount: Optional[float] = None
    fee_percent: Optional[float] = None
    grace_period_days: int = Field(default=5)
    max_fee: Optional[float] = None

class PaymentMethodCreate(BaseModel):
    name: str
    method_type: str
    is_active: bool = True
