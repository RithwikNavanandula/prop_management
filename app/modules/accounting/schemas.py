"""Pydantic schemas for the Accounting module."""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date


class AccountCreate(BaseModel):
    account_code: str = Field(..., min_length=1)
    account_name: str = Field(..., min_length=1)
    account_type: str  # Asset, Liability, Equity, Revenue, Expense
    parent_account_id: Optional[int] = None
    description: Optional[str] = None
    status: str = Field(default="Active")

class AccountUpdate(BaseModel):
    account_name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None

class JournalEntryLineCreate(BaseModel):
    account_id: int
    debit_amount: float = Field(default=0, ge=0)
    credit_amount: float = Field(default=0, ge=0)
    description: Optional[str] = None

class JournalEntryCreate(BaseModel):
    entry_date: date
    reference: Optional[str] = None
    description: Optional[str] = None
    lines: List[JournalEntryLineCreate] = Field(..., min_length=2)

class VendorBillCreate(BaseModel):
    vendor_id: int
    bill_number: str
    bill_date: date
    due_date: date
    total_amount: float = Field(..., gt=0)
    currency: str = Field(default="USD")
    property_id: Optional[int] = None
    description: Optional[str] = None

class DistributionCreate(BaseModel):
    owner_id: int
    property_id: int
    period_start: date
    period_end: date
    gross_revenue: float
    expenses: float = Field(default=0)
    management_fee: float = Field(default=0)

class BankAccountCreate(BaseModel):
    account_name: str
    bank_name: str
    account_number: str
    routing_number: Optional[str] = None
    account_type: str = Field(default="Checking")
    currency: str = Field(default="USD")
    gl_account_id: Optional[int] = None
