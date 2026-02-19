"""Billing models – Invoice, Payment, FX, LateFee."""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Date, Text, Numeric, ForeignKey, JSON
from sqlalchemy.sql import func
from app.database import Base


class LateFeeRule(Base):
    __tablename__ = "late_fee_rules"
    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_org_id = Column(Integer, ForeignKey("tenant_orgs.id"))
    rule_name = Column(String(200), nullable=False)
    fee_type = Column(String(20), default="FlatFee")
    fee_value = Column(Numeric(14, 2), nullable=False)
    grace_period_days = Column(Integer, default=5)
    max_fee_amount = Column(Numeric(14, 2))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())


class PaymentMethod(Base):
    __tablename__ = "payment_methods"
    id = Column(Integer, primary_key=True, autoincrement=True)
    method_name = Column(String(50), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())


class ExchangeRateDaily(Base):
    __tablename__ = "exchange_rates_daily"
    id = Column(Integer, primary_key=True, autoincrement=True)
    rate_date = Column(Date, nullable=False)
    from_currency = Column(String(10), nullable=False)
    to_currency = Column(String(10), nullable=False)
    rate_type = Column(String(20), default="Spot")
    rate = Column(Numeric(18, 8), nullable=False)
    source = Column(String(20), default="Manual")
    is_default = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())


class Invoice(Base):
    __tablename__ = "invoices"
    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_org_id = Column(Integer, ForeignKey("tenant_orgs.id"))
    invoice_number = Column(String(50), nullable=False, unique=True, index=True)
    invoice_type = Column(String(30), default="Rent")
    lease_id = Column(Integer, ForeignKey("leases.id"))
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    property_id = Column(Integer, ForeignKey("properties.id"))
    unit_id = Column(Integer, ForeignKey("units.id"))
    invoice_date = Column(Date, nullable=False)
    due_date = Column(Date, nullable=False)
    posting_date = Column(Date)
    document_currency = Column(String(10), default="USD")
    document_amount = Column(Numeric(14, 2), nullable=False)
    base_currency = Column(String(10), default="USD")
    base_amount = Column(Numeric(14, 2))
    exchange_rate_id = Column(Integer, ForeignKey("exchange_rates_daily.id"))
    exchange_rate_value = Column(Numeric(18, 8))
    fx_difference_amount = Column(Numeric(14, 2), default=0)
    tax_amount = Column(Numeric(14, 2), default=0)
    total_amount = Column(Numeric(14, 2), nullable=False)
    invoice_status = Column(String(20), default="Draft")
    is_reversed = Column(Boolean, default=False)
    reversal_invoice_id = Column(Integer)
    notes = Column(Text)
    created_by = Column(Integer)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class InvoiceLine(Base):
    __tablename__ = "invoice_lines"
    id = Column(Integer, primary_key=True, autoincrement=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=False)
    description = Column(String(500))
    charge_type = Column(String(50))
    quantity = Column(Numeric(10, 2), default=1)
    unit_price = Column(Numeric(14, 2))
    line_amount = Column(Numeric(14, 2))
    tax_rate = Column(Numeric(5, 2), default=0)
    tax_amount = Column(Numeric(14, 2), default=0)
    line_total_amount = Column(Numeric(14, 2))
    account_id = Column(Integer)
    created_at = Column(DateTime, server_default=func.now())


class Payment(Base):
    __tablename__ = "payments"
    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_org_id = Column(Integer, ForeignKey("tenant_orgs.id"))
    payment_number = Column(String(50), nullable=False, unique=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    payment_date = Column(Date, nullable=False)
    amount = Column(Numeric(14, 2), nullable=False)
    currency = Column(String(10), default="USD")
    payment_method_id = Column(Integer, ForeignKey("payment_methods.id"))
    reference_number = Column(String(100))
    bank_account_id = Column(Integer)
    status = Column(String(20), default="Received")
    notes = Column(Text)
    created_by = Column(Integer)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class PaymentAllocation(Base):
    __tablename__ = "payment_allocations"
    id = Column(Integer, primary_key=True, autoincrement=True)
    payment_id = Column(Integer, ForeignKey("payments.id"), nullable=False)
    invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=False)
    allocated_amount = Column(Numeric(14, 2), nullable=False)
    currency = Column(String(10), default="USD")
    created_at = Column(DateTime, server_default=func.now())


class FxRevaluationBatch(Base):
    __tablename__ = "fx_revaluation_batches"
    id = Column(Integer, primary_key=True, autoincrement=True)
    batch_date = Column(Date, nullable=False)
    currency_pair = Column(String(20))
    rate_used = Column(Numeric(18, 8))
    batch_type = Column(String(20), default="Unrealized")
    total_gain_loss = Column(Numeric(14, 2), default=0)
    generated_by = Column(Integer)
    created_at = Column(DateTime, server_default=func.now())


class FxRevaluationLine(Base):
    __tablename__ = "fx_revaluation_lines"
    id = Column(Integer, primary_key=True, autoincrement=True)
    batch_id = Column(Integer, ForeignKey("fx_revaluation_batches.id"), nullable=False)
    invoice_id = Column(Integer, ForeignKey("invoices.id"))
    lease_id = Column(Integer, ForeignKey("leases.id"))
    original_amount = Column(Numeric(14, 2))
    revalued_amount = Column(Numeric(14, 2))
    gain_loss = Column(Numeric(14, 2))
    created_at = Column(DateTime, server_default=func.now())


class FxRateSnapshot(Base):
    __tablename__ = "fx_rate_snapshots"
    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_org_id = Column(Integer, ForeignKey("tenant_orgs.id"), nullable=False)
    snapshot_date = Column(Date, nullable=False, index=True)
    from_currency = Column(String(10), nullable=False)
    to_currency = Column(String(10), nullable=False)
    rate = Column(Numeric(18, 8), nullable=False)
    source = Column(String(30), default="Manual")
    exchange_rate_daily_id = Column(Integer, ForeignKey("exchange_rates_daily.id"))
    created_by = Column(Integer)
    created_at = Column(DateTime, server_default=func.now())


class MultiCurrencyLedgerEntry(Base):
    __tablename__ = "multi_currency_ledger_entries"
    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_org_id = Column(Integer, ForeignKey("tenant_orgs.id"), nullable=False)
    legal_entity_id = Column(Integer, ForeignKey("legal_entities.id"))
    reference_type = Column(String(50), nullable=False)  # Invoice/Payment/Revaluation
    reference_id = Column(Integer, nullable=False)
    posting_date = Column(Date, nullable=False)
    txn_currency = Column(String(10), nullable=False)
    txn_amount = Column(Numeric(14, 2), nullable=False)
    base_currency = Column(String(10), nullable=False)
    base_amount = Column(Numeric(14, 2), nullable=False)
    fx_rate = Column(Numeric(18, 8), nullable=False)
    fx_snapshot_id = Column(Integer, ForeignKey("fx_rate_snapshots.id"))
    entry_side = Column(String(10), default="Debit")  # Debit/Credit
    notes = Column(Text)
    created_by = Column(Integer)
    created_at = Column(DateTime, server_default=func.now())
