"""Accounting models – ChartOfAccount, JournalEntry, VendorBill, OwnerDistribution, BankAccount."""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Date, Numeric, ForeignKey, Text
from sqlalchemy.sql import func
from app.database import Base


class ChartOfAccount(Base):
    __tablename__ = "chart_of_accounts"
    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_org_id = Column(Integer, ForeignKey("tenant_orgs.id"))
    account_code = Column(String(20), nullable=False, index=True)
    account_name = Column(String(200), nullable=False)
    account_type = Column(String(30), nullable=False)
    sub_type = Column(String(50))
    parent_account_id = Column(Integer, ForeignKey("chart_of_accounts.id"))
    is_posting_account = Column(Boolean, default=True)
    currency = Column(String(10), default="USD")
    status = Column(String(20), default="Active")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class GLAccountBalance(Base):
    __tablename__ = "gl_account_balances"
    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, ForeignKey("chart_of_accounts.id"), nullable=False)
    period_id = Column(String(10))
    opening_balance = Column(Numeric(18, 2), default=0)
    debits = Column(Numeric(18, 2), default=0)
    credits = Column(Numeric(18, 2), default=0)
    closing_balance = Column(Numeric(18, 2), default=0)
    currency = Column(String(10), default="USD")
    created_at = Column(DateTime, server_default=func.now())


class JournalEntry(Base):
    __tablename__ = "journal_entries"
    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_org_id = Column(Integer, ForeignKey("tenant_orgs.id"))
    journal_number = Column(String(50), nullable=False, unique=True)
    entry_date = Column(Date, nullable=False)
    period_id = Column(String(10))
    currency = Column(String(10), default="USD")
    total_debit = Column(Numeric(18, 2), default=0)
    total_credit = Column(Numeric(18, 2), default=0)
    source_module = Column(String(30))
    reference_id = Column(Integer)
    description = Column(Text)
    status = Column(String(20), default="Posted")
    created_by = Column(Integer)
    created_at = Column(DateTime, server_default=func.now())


class JournalEntryLine(Base):
    __tablename__ = "journal_entry_lines"
    id = Column(Integer, primary_key=True, autoincrement=True)
    journal_entry_id = Column(Integer, ForeignKey("journal_entries.id"), nullable=False)
    account_id = Column(Integer, ForeignKey("chart_of_accounts.id"), nullable=False)
    debit_amount = Column(Numeric(18, 2), default=0)
    credit_amount = Column(Numeric(18, 2), default=0)
    property_id = Column(Integer, ForeignKey("properties.id"))
    unit_id = Column(Integer, ForeignKey("units.id"))
    lease_id = Column(Integer, ForeignKey("leases.id"))
    tenant_id = Column(Integer, ForeignKey("tenants.id"))
    owner_id = Column(Integer, ForeignKey("owners.id"))
    cost_center_id = Column(String(50))
    project_id = Column(String(50))
    narration = Column(String(500))
    created_at = Column(DateTime, server_default=func.now())


class VendorBill(Base):
    __tablename__ = "vendor_bills"
    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_org_id = Column(Integer, ForeignKey("tenant_orgs.id"))
    bill_number = Column(String(50), nullable=False, unique=True)
    vendor_id = Column(Integer, ForeignKey("vendors.id"), nullable=False)
    property_id = Column(Integer, ForeignKey("properties.id"))
    bill_date = Column(Date, nullable=False)
    due_date = Column(Date)
    amount = Column(Numeric(14, 2), nullable=False)
    currency = Column(String(10), default="USD")
    description = Column(Text)
    status = Column(String(20), default="Pending")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class OwnerDistribution(Base):
    __tablename__ = "owner_distributions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_org_id = Column(Integer, ForeignKey("tenant_orgs.id"))
    owner_id = Column(Integer, ForeignKey("owners.id"), nullable=False)
    property_id = Column(Integer, ForeignKey("properties.id"), nullable=False)
    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)
    gross_income = Column(Numeric(14, 2), default=0)
    expenses = Column(Numeric(14, 2), default=0)
    management_fee = Column(Numeric(14, 2), default=0)
    net_distribution = Column(Numeric(14, 2), default=0)
    currency = Column(String(10), default="USD")
    payment_date = Column(Date)
    status = Column(String(20), default="Pending")
    created_at = Column(DateTime, server_default=func.now())


class BankAccount(Base):
    __tablename__ = "bank_accounts"
    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_org_id = Column(Integer, ForeignKey("tenant_orgs.id"))
    account_name = Column(String(200), nullable=False)
    bank_name = Column(String(200))
    account_number = Column(String(100))
    routing_number = Column(String(50))
    currency = Column(String(10), default="USD")
    current_balance = Column(Numeric(18, 2), default=0)
    property_id = Column(Integer, ForeignKey("properties.id"))
    status = Column(String(20), default="Active")
    created_at = Column(DateTime, server_default=func.now())


class BankReconciliation(Base):
    __tablename__ = "bank_reconciliations"
    id = Column(Integer, primary_key=True, autoincrement=True)
    bank_account_id = Column(Integer, ForeignKey("bank_accounts.id"), nullable=False)
    statement_date = Column(Date, nullable=False)
    statement_balance = Column(Numeric(18, 2))
    book_balance = Column(Numeric(18, 2))
    difference = Column(Numeric(18, 2))
    status = Column(String(20), default="InProgress")
    reconciled_by = Column(Integer)
    created_at = Column(DateTime, server_default=func.now())


class OwnerStatement(Base):
    __tablename__ = "owner_statements"
    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_org_id = Column(Integer, ForeignKey("tenant_orgs.id"))
    owner_id = Column(Integer, ForeignKey("owners.id"), nullable=False)
    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)
    total_income = Column(Numeric(14, 2), default=0)
    total_expenses = Column(Numeric(14, 2), default=0)
    net_amount = Column(Numeric(14, 2), default=0)
    currency = Column(String(10), default="USD")
    status = Column(String(20), default="Draft")
    statement_file_path = Column(String(500))
    created_at = Column(DateTime, server_default=func.now())


class VendorInvoice(Base):
    __tablename__ = "vendor_invoices"
    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_org_id = Column(Integer, ForeignKey("tenant_orgs.id"))
    vendor_id = Column(Integer, ForeignKey("vendors.id"), nullable=False)
    work_order_id = Column(Integer, ForeignKey("work_orders.id"))
    invoice_number = Column(String(50), nullable=False, unique=True, index=True)
    invoice_date = Column(Date, nullable=False)
    due_date = Column(Date)
    amount = Column(Numeric(14, 2), nullable=False)
    currency = Column(String(10), default="USD")
    status = Column(String(20), default="Pending")
    invoice_file_path = Column(String(500))
    created_at = Column(DateTime, server_default=func.now())
