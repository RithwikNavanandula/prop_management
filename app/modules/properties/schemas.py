"""Pydantic schemas for the Properties module."""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import date


# --- Property ---
class PropertyCreate(BaseModel):
    property_name: str = Field(..., min_length=1, max_length=200)
    property_code: str = Field(..., min_length=1, max_length=50)
    property_type: str = Field(default="Residential")
    status: str = Field(default="Active")
    tenant_org_id: Optional[int] = None
    region_id: Optional[int] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    zip_code: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    total_area_sqft: Optional[float] = None
    year_built: Optional[int] = None
    description: Optional[str] = None

class PropertyUpdate(BaseModel):
    property_name: Optional[str] = None
    property_type: Optional[str] = None
    status: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    zip_code: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    total_area_sqft: Optional[float] = None
    year_built: Optional[int] = None
    description: Optional[str] = None


# --- Unit ---
class UnitCreate(BaseModel):
    unit_number: str = Field(..., min_length=1, max_length=50)
    unit_type: Optional[str] = Field(default="Apartment")
    current_status: str = Field(default="Vacant")
    tenant_org_id: Optional[int] = None
    building_id: Optional[int] = None
    floor_id: Optional[int] = None
    area_sqft: Optional[float] = None
    area_sqm: Optional[float] = None
    bedrooms: Optional[int] = None
    bathrooms: Optional[int] = None
    rooms: Optional[int] = None
    balconies: Optional[int] = None
    parking_slots: Optional[int] = None
    market_rent: Optional[float] = None
    ceiling_height_ft: Optional[float] = None
    load_capacity_tons: Optional[float] = None
    min_lease_term: Optional[int] = None
    max_occupancy: Optional[int] = None
    furnishing_status: Optional[str] = None
    facing_direction: Optional[str] = None

class UnitUpdate(BaseModel):
    unit_number: Optional[str] = None
    unit_type: Optional[str] = None
    current_status: Optional[str] = None
    building_id: Optional[int] = None
    floor_id: Optional[int] = None
    area_sqft: Optional[float] = None
    area_sqm: Optional[float] = None
    bedrooms: Optional[int] = None
    bathrooms: Optional[int] = None
    market_rent: Optional[float] = None


# --- Building ---
class BuildingCreate(BaseModel):
    building_name: str = Field(..., min_length=1, max_length=200)
    building_code: Optional[str] = None
    status: str = Field(default="Active")
    total_floors: Optional[int] = None
    total_units: Optional[int] = None
    year_built: Optional[int] = None

class BuildingUpdate(BaseModel):
    building_name: Optional[str] = None
    building_code: Optional[str] = None
    status: Optional[str] = None
    total_floors: Optional[int] = None
    total_units: Optional[int] = None


# --- Floor ---
class FloorCreate(BaseModel):
    floor_name: str = Field(..., min_length=1)
    floor_number: Optional[int] = None
    total_units: Optional[int] = None

class FloorUpdate(BaseModel):
    floor_name: Optional[str] = None
    floor_number: Optional[int] = None


# --- Owner ---
class OwnerCreate(BaseModel):
    first_name: str = Field(..., min_length=1)
    last_name: str = Field(..., min_length=1)
    email: Optional[str] = None
    phone: Optional[str] = None
    owner_type: Optional[str] = Field(default="Individual")
    company_name: Optional[str] = None
    tax_id: Optional[str] = None
    tenant_org_id: Optional[int] = None

class OwnerUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None


# --- Tenant ---
class TenantCreate(BaseModel):
    first_name: str = Field(..., min_length=1)
    last_name: str = Field(..., min_length=1)
    tenant_code: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    id_type: Optional[str] = None
    id_number: Optional[str] = None
    tenant_org_id: Optional[int] = None

class TenantUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None


# --- Vendor ---
class VendorCreate(BaseModel):
    vendor_name: str = Field(..., min_length=1)
    vendor_code: Optional[str] = None
    category: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    tenant_org_id: Optional[int] = None

class VendorUpdate(BaseModel):
    vendor_name: Optional[str] = None
    category: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None


# --- Asset ---
class AssetCreate(BaseModel):
    asset_name: str = Field(..., min_length=1)
    asset_type: Optional[str] = None
    serial_number: Optional[str] = None
    purchase_date: Optional[date] = None
    purchase_cost: Optional[float] = None
    condition: Optional[str] = Field(default="Good")
    warranty_expiry: Optional[date] = None

class AssetUpdate(BaseModel):
    asset_name: Optional[str] = None
    asset_type: Optional[str] = None
    condition: Optional[str] = None
