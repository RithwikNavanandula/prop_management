"""Core property models – TenantOrg, Region, Property, Building, Floor, Unit, UnitAsset, Owner, Tenant, Vendor, StaffUser."""
from sqlalchemy import (Column, Integer, BigInteger, String, Boolean, DateTime, Date,
                         Text, Float, Numeric, ForeignKey, JSON, Index)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base


class TenantOrg(Base):
    __tablename__ = "tenant_orgs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    org_name = Column(String(200), nullable=False)
    org_code = Column(String(50), unique=True, nullable=False)
    subdomain = Column(String(100), unique=True)
    plan = Column(String(50), default="standard")
    status = Column(String(20), default="Active")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class Region(Base):
    __tablename__ = "regions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_org_id = Column(Integer, ForeignKey("tenant_orgs.id"))
    region_code = Column(String(50), nullable=False)
    region_name = Column(String(200), nullable=False)
    country = Column(String(100))
    currency = Column(String(10), default="USD")
    timezone = Column(String(50))
    status = Column(String(20), default="Active")
    is_deleted = Column(Boolean, default=False)
    created_by = Column(Integer)
    created_at = Column(DateTime, server_default=func.now())
    updated_by = Column(Integer)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class Property(Base):
    __tablename__ = "properties"
    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_org_id = Column(Integer, ForeignKey("tenant_orgs.id"))
    region_id = Column(Integer, ForeignKey("regions.id"))
    property_code = Column(String(50), nullable=False, index=True)
    property_name = Column(String(300), nullable=False)
    property_type = Column(String(50), default="Residential")  # Residential/Commercial/Mixed
    address_line1 = Column(String(300))
    address_line2 = Column(String(300))
    city = Column(String(100))
    state = Column(String(100))
    country = Column(String(100))
    postal_code = Column(String(20))
    latitude = Column(Float)
    longitude = Column(Float)
    total_units = Column(Integer, default=0)
    total_area_sqft = Column(Numeric(12, 2))
    zoning_category = Column(String(100))
    commercial_category = Column(String(100))
    grade = Column(String(10))
    common_area_factor = Column(Numeric(5, 4))
    parking_spaces = Column(Integer, default=0)
    business_hours = Column(String(100))
    fit_out_standard = Column(String(200))
    year_built = Column(Integer)
    photo_url = Column(String(500))
    description = Column(Text)
    status = Column(String(20), default="Active")
    is_deleted = Column(Boolean, default=False)
    created_by = Column(Integer)
    created_at = Column(DateTime, server_default=func.now())
    updated_by = Column(Integer)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    buildings = relationship("Building", backref="property", lazy="dynamic")
    units = relationship("Unit", backref="property", lazy="dynamic")


class Building(Base):
    __tablename__ = "buildings"
    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_org_id = Column(Integer, ForeignKey("tenant_orgs.id"))
    property_id = Column(Integer, ForeignKey("properties.id"), nullable=False)
    building_code = Column(String(50), nullable=False)
    building_name = Column(String(200), nullable=False)
    floors_count = Column(Integer, default=1)
    year_built = Column(Integer)
    status = Column(String(20), default="Active")
    is_deleted = Column(Boolean, default=False)
    created_by = Column(Integer)
    created_at = Column(DateTime, server_default=func.now())
    updated_by = Column(Integer)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    floors = relationship("Floor", backref="building", lazy="dynamic")


class Floor(Base):
    __tablename__ = "floors"
    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_org_id = Column(Integer, ForeignKey("tenant_orgs.id"))
    building_id = Column(Integer, ForeignKey("buildings.id"), nullable=False)
    floor_number = Column(Integer, nullable=False)
    floor_name = Column(String(100))
    total_units = Column(Integer, default=0)
    floor_area_sqft = Column(Numeric(12, 2))
    status = Column(String(20), default="Active")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class Unit(Base):
    __tablename__ = "units"
    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_org_id = Column(Integer, ForeignKey("tenant_orgs.id"))
    property_id = Column(Integer, ForeignKey("properties.id"), nullable=False)
    building_id = Column(Integer, ForeignKey("buildings.id"))
    floor_id = Column(Integer, ForeignKey("floors.id"))
    unit_number = Column(String(50), nullable=False)
    unit_name = Column(String(200))
    unit_type = Column(String(50), default="1BHK")
    area_sqft = Column(Numeric(10, 2))
    area_sqm = Column(Numeric(10, 2))
    bedrooms = Column(Integer, default=0)
    bathrooms = Column(Integer, default=0)
    rooms = Column(Integer, default=0)
    balconies = Column(Integer, default=0)
    parking_slots = Column(Integer, default=0)
    ceiling_height_ft = Column(Numeric(5, 2))
    load_capacity_tons = Column(Numeric(8, 2))
    hvac_type = Column(String(50))
    current_status = Column(String(30), default="Vacant")
    market_rent = Column(Numeric(12, 2))
    min_lease_term = Column(Integer, default=12)
    max_occupancy = Column(Integer, default=1)
    usage_type = Column(String(50))
    qr_code_value = Column(String(500))
    qr_code_image_url = Column(String(500))
    qr_code_version = Column(Integer, default=1)
    qr_code_last_generated_at = Column(DateTime)
    photo_url = Column(String(500))
    description = Column(Text)
    status = Column(String(20), default="Active")
    is_deleted = Column(Boolean, default=False)
    created_by = Column(Integer)
    created_at = Column(DateTime, server_default=func.now())
    updated_by = Column(Integer)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    primary_tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True)
    assets = relationship("Asset", backref="unit", lazy="dynamic")


class Asset(Base):
    __tablename__ = "assets"
    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_org_id = Column(Integer, ForeignKey("tenant_orgs.id"))
    asset_number = Column(String(50), nullable=False, index=True)
    property_id = Column(Integer, ForeignKey("properties.id"), nullable=True)
    unit_id = Column(Integer, ForeignKey("units.id"), nullable=True)
    asset_category = Column(String(50))
    asset_type = Column(String(100))
    asset_name = Column(String(200), nullable=False)
    description = Column(Text)
    serial_number = Column(String(100))
    manufacturer = Column(String(200))
    model = Column(String(200))
    purchase_date = Column(Date)
    purchase_price = Column(Numeric(12, 2))
    warranty_expiry_date = Column(Date)
    condition_status = Column(String(30), default="Good")
    assigned_qr_value = Column(String(500))
    photo_url = Column(String(500))
    last_inspection_date = Column(Date)
    next_inspection_date = Column(Date)
    allocated_at = Column(DateTime, nullable=True)
    status = Column(String(20), default="Active")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


# Keep backward compatibility alias
UnitAsset = Asset


class Owner(Base):
    __tablename__ = "owners"
    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_org_id = Column(Integer, ForeignKey("tenant_orgs.id"))
    owner_code = Column(String(50), nullable=False)
    owner_type = Column(String(30), default="Individual")
    first_name = Column(String(100))
    last_name = Column(String(100))
    company_name = Column(String(300))
    email = Column(String(255))
    phone = Column(String(50))
    tax_id = Column(String(50))
    bank_account_name = Column(String(200))
    bank_account_number = Column(String(100))
    bank_name = Column(String(200))
    routing_number = Column(String(50))
    status = Column(String(20), default="Active")
    is_deleted = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class PropertyOwnerLink(Base):
    __tablename__ = "property_owner_links"
    id = Column(Integer, primary_key=True, autoincrement=True)
    property_id = Column(Integer, ForeignKey("properties.id"), nullable=False)
    owner_id = Column(Integer, ForeignKey("owners.id"), nullable=False)
    ownership_percent = Column(Numeric(5, 2), default=100.00)
    effective_from = Column(Date)
    effective_to = Column(Date)
    status = Column(String(20), default="Active")
    created_at = Column(DateTime, server_default=func.now())


class Tenant(Base):
    __tablename__ = "tenants"
    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_org_id = Column(Integer, ForeignKey("tenant_orgs.id"))
    tenant_code = Column(String(50), nullable=False)
    tenant_type = Column(String(30), default="Individual")
    first_name = Column(String(100))
    last_name = Column(String(100))
    company_name = Column(String(300))
    email = Column(String(255))
    phone = Column(String(50))
    emergency_contact = Column(String(100))
    id_type = Column(String(50))
    id_number = Column(String(100))
    date_of_birth = Column(Date)
    status = Column(String(20), default="Active")
    is_deleted = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class Vendor(Base):
    __tablename__ = "vendors"
    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_org_id = Column(Integer, ForeignKey("tenant_orgs.id"))
    vendor_code = Column(String(50), nullable=False)
    company_name = Column(String(300), nullable=False)
    contact_person = Column(String(200))
    email = Column(String(255))
    phone = Column(String(50))
    service_category = Column(String(100))
    license_number = Column(String(100))
    insurance_expiry = Column(Date)
    rating = Column(Numeric(3, 2))
    status = Column(String(20), default="Active")
    is_deleted = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class StaffUser(Base):
    __tablename__ = "staff_users"
    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_org_id = Column(Integer, ForeignKey("tenant_orgs.id"))
    employee_code = Column(String(50), nullable=False)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100))
    email = Column(String(255))
    phone = Column(String(50))
    role_id = Column(Integer, ForeignKey("roles.id"))
    department = Column(String(100))
    hire_date = Column(Date)
    status = Column(String(20), default="Active")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
