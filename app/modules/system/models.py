"""System models - geo, tax, org settings, payments."""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Date, Numeric, ForeignKey, JSON, Text
from sqlalchemy.sql import func
from app.database import Base


class Country(Base):
    __tablename__ = "countries"
    id = Column(Integer, primary_key=True, autoincrement=True)
    country_code = Column(String(2), nullable=False, unique=True)
    country_name = Column(String(100), nullable=False)
    iso3 = Column(String(3))
    default_currency_code = Column(String(10))
    default_timezone = Column(String(50))
    phone_code = Column(String(10))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())


class Currency(Base):
    __tablename__ = "currencies"
    id = Column(Integer, primary_key=True, autoincrement=True)
    currency_code = Column(String(10), nullable=False, unique=True)
    currency_name = Column(String(100), nullable=False)
    symbol = Column(String(10))
    minor_units = Column(Integer, default=2)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())


class OrgSettings(Base):
    __tablename__ = "org_settings"
    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_org_id = Column(Integer, ForeignKey("tenant_orgs.id"), unique=True, nullable=False)
    base_currency = Column(String(10), default="USD")
    country_code = Column(String(2))
    timezone = Column(String(50), default="UTC")
    locale = Column(String(10), default="en-US")
    fiscal_year_start_month = Column(Integer, default=1)
    tax_inclusive = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class TaxCode(Base):
    __tablename__ = "tax_codes"
    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_org_id = Column(Integer, ForeignKey("tenant_orgs.id"))
    code = Column(String(30), nullable=False)
    name = Column(String(200), nullable=False)
    country_code = Column(String(2))
    tax_type = Column(String(30), default="VAT")
    is_compound = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())


class TaxRate(Base):
    __tablename__ = "tax_rates"
    id = Column(Integer, primary_key=True, autoincrement=True)
    tax_code_id = Column(Integer, ForeignKey("tax_codes.id"), nullable=False)
    country_code = Column(String(2))
    region_code = Column(String(50))
    rate_percent = Column(Numeric(6, 3), nullable=False)
    effective_from = Column(Date)
    effective_to = Column(Date)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())


class InvoiceLineTax(Base):
    __tablename__ = "invoice_line_taxes"
    id = Column(Integer, primary_key=True, autoincrement=True)
    invoice_line_id = Column(Integer, ForeignKey("invoice_lines.id"), nullable=False)
    tax_code_id = Column(Integer, ForeignKey("tax_codes.id"))
    tax_rate_id = Column(Integer, ForeignKey("tax_rates.id"))
    rate_percent = Column(Numeric(6, 3))
    tax_amount = Column(Numeric(14, 2), default=0)
    created_at = Column(DateTime, server_default=func.now())


class PaymentProvider(Base):
    __tablename__ = "payment_providers"
    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_org_id = Column(Integer, ForeignKey("tenant_orgs.id"), nullable=False)
    provider_name = Column(String(50), nullable=False)
    environment = Column(String(20), default="test")
    is_active = Column(Boolean, default=True)
    settings_json = Column(JSON)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class PaymentIntent(Base):
    __tablename__ = "payment_intents"
    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_org_id = Column(Integer, ForeignKey("tenant_orgs.id"), nullable=False)
    provider_id = Column(Integer, ForeignKey("payment_providers.id"))
    invoice_id = Column(Integer, ForeignKey("invoices.id"))
    amount = Column(Numeric(14, 2), nullable=False)
    currency = Column(String(10), default="USD")
    status = Column(String(30), default="Created")
    external_id = Column(String(200))
    raw_response = Column(Text)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
