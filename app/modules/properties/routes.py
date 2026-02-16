"""Property CRUD routes."""
import logging
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import Optional
from decimal import Decimal, InvalidOperation
from app.database import get_db
from app.auth.dependencies import get_current_user, require_permissions
from app.auth.models import UserAccount
from app.modules.properties.models import (
    Property, Building, Floor, Unit, Asset, UnitAsset, Owner, Tenant, Vendor,
    PropertyOwnerLink, Region, TenantOrg
)
from app.utils.qrcode_service import generate_qr_code
from app.modules.compliance.models import Document
import os
import shutil
from datetime import datetime

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/api/properties",
    tags=["Properties"],
    dependencies=[Depends(require_permissions(["properties", "portfolio"]))],
)

NULL_LIKE_STRINGS = {"", "null", "none", "nan"}


def _coerce_column_value(column, value):
    if value is None:
        return None

    if isinstance(value, str):
        value = value.strip()
        if value.lower() in NULL_LIKE_STRINGS:
            return None

    try:
        python_type = column.type.python_type
    except (NotImplementedError, AttributeError):
        return value

    if python_type is bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        if isinstance(value, str):
            lowered = value.lower()
            if lowered in {"true", "1", "yes", "y", "on"}:
                return True
            if lowered in {"false", "0", "no", "n", "off"}:
                return False
        raise ValueError("invalid boolean")

    if python_type in (int, float, Decimal):
        try:
            return python_type(value)
        except (TypeError, ValueError, InvalidOperation) as exc:
            raise ValueError("invalid numeric value") from exc

    return value


def _sanitize_model_payload(model, data: dict, blocked_fields: set | None = None) -> dict:
    blocked_fields = blocked_fields or set()
    cleaned = {}
    errors = []

    for key, value in data.items():
        if key in blocked_fields:
            continue
        column = model.__table__.columns.get(key)
        if column is None:
            continue
        try:
            cleaned[key] = _coerce_column_value(column, value)
        except ValueError:
            errors.append(key)

    if errors:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid values for fields: {', '.join(errors)}"
        )
    return cleaned


@router.get("/tenant-orgs")
def list_tenant_orgs(db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    items = db.query(TenantOrg).all()
    return {"total": len(items), "items": [_org_dict(o) for o in items]}


@router.get("")
def list_properties(
    search: Optional[str] = None,
    property_type: Optional[str] = None,
    status: Optional[str] = "Active",
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    q = db.query(Property).filter(Property.is_deleted == False)
    # Multi-tenant isolation
    if user.tenant_org_id:
        q = q.filter(Property.tenant_org_id == user.tenant_org_id)
    if status:
        q = q.filter(Property.status == status)
    if property_type:
        q = q.filter(Property.property_type == property_type)
    if search:
        q = q.filter(or_(
            Property.property_name.ilike(f"%{search}%"),
            Property.property_code.ilike(f"%{search}%"),
            Property.city.ilike(f"%{search}%"),
        ))
    total = q.count()
    items = q.order_by(Property.id.desc()).offset(skip).limit(limit).all()
    return {"total": total, "items": [_prop_dict(p) for p in items]}


@router.post("", status_code=201)
def create_property(data: dict, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    clean_data = _sanitize_model_payload(Property, data, blocked_fields={"id", "created_at", "updated_at", "created_by", "updated_by"})

    # Enforce tenant scope automatically for tenant-scoped users.
    if user.tenant_org_id:
        clean_data["tenant_org_id"] = user.tenant_org_id

    prop = Property(**clean_data)
    prop.created_by = user.id
    db.add(prop)
    db.commit()
    db.refresh(prop)
    return _prop_dict(prop)


@router.get("/{prop_id}")
def get_property(prop_id: int, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    prop = db.query(Property).filter(Property.id == prop_id, Property.is_deleted == False).first()
    if not prop:
        raise HTTPException(404, "Property not found")
    return _prop_dict(prop)


@router.put("/{prop_id}")
def update_property(prop_id: int, data: dict, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    prop = db.query(Property).filter(Property.id == prop_id).first()
    if not prop:
        raise HTTPException(404, "Property not found")

    # Prevent cross-tenant mutation for tenant-scoped users.
    if user.tenant_org_id and prop.tenant_org_id != user.tenant_org_id:
        raise HTTPException(404, "Property not found")

    clean_data = _sanitize_model_payload(Property, data, blocked_fields={"id", "created_at", "updated_at", "created_by", "updated_by"})
    if user.tenant_org_id:
        clean_data["tenant_org_id"] = user.tenant_org_id

    for k, v in clean_data.items():
        setattr(prop, k, v)

    prop.updated_by = user.id
    db.commit()
    db.refresh(prop)
    return _prop_dict(prop)


@router.delete("/{prop_id}")
def delete_property(prop_id: int, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    prop = db.query(Property).filter(Property.id == prop_id).first()
    if not prop:
        raise HTTPException(404, "Property not found")
    prop.is_deleted = True
    prop.status = "Inactive"
    db.commit()
    return {"message": "Property deleted"}


# --- Units ---
@router.get("/{prop_id}/units")
def list_units(prop_id: int, status: Optional[str] = None, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    q = db.query(Unit).filter(Unit.property_id == prop_id, Unit.is_deleted == False)
    if status:
        q = q.filter(Unit.current_status == status)
    items = q.order_by(Unit.unit_number).all()
    return {"total": len(items), "items": [_unit_dict(u) for u in items]}


@router.get("/{prop_id}/units/{unit_id}")
def get_unit(prop_id: int, unit_id: int, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    unit = db.query(Unit).filter(Unit.id == unit_id, Unit.property_id == prop_id, Unit.is_deleted == False).first()
    if not unit:
        raise HTTPException(404, "Unit not found")
    return _unit_dict(unit)


@router.post("/{prop_id}/units", status_code=201)
def create_unit(prop_id: int, data: dict, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    # 1. Prepare data dictionary with strict type conversion
    unit_data = {}
    for col in Unit.__table__.columns:
        k = col.name
        if k in ("id", "created_at", "updated_at", "property_id"):
            continue
            
        v = data.get(k)
        # Handle null-ish values
        if v in (None, "", "NaN", "null"):
            unit_data[k] = None
            continue
            
        # Type conversion
        if k in ("tenant_org_id", "building_id", "floor_id", "primary_tenant_id", "bedrooms", "bathrooms", "rooms", "balconies", "parking_slots", "min_lease_term", "max_occupancy"):
            try:
                unit_data[k] = int(v)
            except (ValueError, TypeError):
                unit_data[k] = None
        elif k in ("area_sqft", "area_sqm", "ceiling_height_ft", "load_capacity_tons", "market_rent"):
            try:
                unit_data[k] = float(v)
            except (ValueError, TypeError):
                unit_data[k] = None
        else:
            unit_data[k] = v

    unit = Unit(**unit_data)
    unit.property_id = prop_id
    unit.created_by = user.id
    db.add(unit)
    db.commit()
    db.refresh(unit)
    return _unit_dict(unit)


@router.put("/{prop_id}/units/{unit_id}")
def update_unit(prop_id: int, unit_id: int, data: dict, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    unit = db.query(Unit).filter(Unit.id == unit_id, Unit.property_id == prop_id).first()
    if not unit:
        raise HTTPException(404, "Unit not found")
    for k, v in data.items():
        if hasattr(unit, k) and k not in ("id", "created_at", "property_id"):
            setattr(unit, k, v)
    unit.updated_by = user.id
    db.commit()
    db.refresh(unit)
    return _unit_dict(unit)


@router.delete("/{prop_id}/units/{unit_id}")
def delete_unit(prop_id: int, unit_id: int, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    unit = db.query(Unit).filter(Unit.id == unit_id, Unit.property_id == prop_id).first()
    if not unit:
        raise HTTPException(404, "Unit not found")
    unit.is_deleted = True
    unit.status = "Inactive"
    db.commit()
    return {"message": "Unit deleted"}


@router.post("/{prop_id}/units/{unit_id}/qrcode")
def generate_unit_qrcode(prop_id: int, unit_id: int, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    unit = db.query(Unit).filter(Unit.id == unit_id, Unit.property_id == prop_id).first()
    if not unit:
        raise HTTPException(404, "Unit not found")
        
    qr_content = f"UNIT:{unit.unit_number}"
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    filename = f"unit_{unit.id}_{timestamp}.png"
    
    try:
        url = generate_qr_code(qr_content, filename)
        unit.qr_code_image_url = url
        unit.qr_code_value = qr_content
        unit.qr_code_last_generated_at = datetime.now()
        db.commit()
        db.refresh(unit)
        return _unit_dict(unit)
    except Exception as e:
        raise HTTPException(500, f"Failed to generate QR code: {str(e)}")


# --- Buildings ---
@router.get("/{prop_id}/buildings")
def list_buildings(prop_id: int, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    items = db.query(Building).filter(Building.property_id == prop_id, Building.is_deleted == False).all()
    return {"total": len(items), "items": [_bldg_dict(b) for b in items]}


@router.post("/{prop_id}/buildings", status_code=201)
def create_building(prop_id: int, data: dict, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    bldg = Building(**{k: v for k, v in data.items() if hasattr(Building, k)})
    bldg.property_id = prop_id
    bldg.created_by = user.id
    db.add(bldg)
    db.commit()
    db.refresh(bldg)
    return _bldg_dict(bldg)


@router.put("/{prop_id}/buildings/{bldg_id}")
def update_building(prop_id: int, bldg_id: int, data: dict, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    bldg = db.query(Building).filter(Building.id == bldg_id, Building.property_id == prop_id).first()
    if not bldg:
        raise HTTPException(404, "Building not found")
    for k, v in data.items():
        if hasattr(bldg, k) and k not in ("id", "created_at", "property_id"):
            setattr(bldg, k, v)
    bldg.updated_by = user.id
    db.commit()
    db.refresh(bldg)
    return _bldg_dict(bldg)


@router.delete("/{prop_id}/buildings/{bldg_id}")
def delete_building(prop_id: int, bldg_id: int, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    bldg = db.query(Building).filter(Building.id == bldg_id, Building.property_id == prop_id).first()
    if not bldg:
        raise HTTPException(404, "Building not found")
    bldg.is_deleted = True
    bldg.status = "Inactive"
    db.commit()
    return {"message": "Building deleted"}


# --- Floors ---
@router.get("/{prop_id}/buildings/{bldg_id}/floors")
def list_floors(prop_id: int, bldg_id: int, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    items = db.query(Floor).filter(Floor.building_id == bldg_id).all()
    return {"total": len(items), "items": [_floor_dict(f) for f in items]}


@router.post("/{prop_id}/buildings/{bldg_id}/floors", status_code=201)
def create_floor(prop_id: int, bldg_id: int, data: dict, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    floor = Floor(**{k: v for k, v in data.items() if hasattr(Floor, k)})
    floor.building_id = bldg_id
    db.add(floor)
    db.commit()
    db.refresh(floor)
    return _floor_dict(floor)


@router.put("/{prop_id}/buildings/{bldg_id}/floors/{floor_id}")
def update_floor(prop_id: int, bldg_id: int, floor_id: int, data: dict, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    floor = db.query(Floor).filter(Floor.id == floor_id, Floor.building_id == bldg_id).first()
    if not floor:
        raise HTTPException(404, "Floor not found")
    for k, v in data.items():
        if hasattr(floor, k) and k not in ("id", "created_at", "building_id"):
            setattr(floor, k, v)
    db.commit()
    db.refresh(floor)
    return _floor_dict(floor)


@router.delete("/{prop_id}/buildings/{bldg_id}/floors/{floor_id}")
def delete_floor(prop_id: int, bldg_id: int, floor_id: int, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    floor = db.query(Floor).filter(Floor.id == floor_id, Floor.building_id == bldg_id).first()
    if not floor:
        raise HTTPException(404, "Floor not found")
    db.delete(floor)
    db.commit()
    return {"message": "Floor deleted"}


# --- Unit Assets (nested under properties – backward compat) ---
@router.get("/{prop_id}/units/{unit_id}/assets")
def list_unit_assets(prop_id: int, unit_id: int, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    items = db.query(Asset).filter(Asset.unit_id == unit_id).all()
    return {"total": len(items), "items": [_asset_dict(a) for a in items]}


@router.post("/{prop_id}/units/{unit_id}/assets", status_code=201)
def create_unit_asset(prop_id: int, unit_id: int, data: dict, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    asset = Asset(**{k: v for k, v in data.items() if hasattr(Asset, k)})
    asset.unit_id = unit_id
    asset.property_id = prop_id
    asset.allocated_at = datetime.now()
    if not asset.asset_number:
        count = db.query(Asset).count()
        asset.asset_number = f"AST-{count + 1:05d}"
    if user.tenant_org_id:
        asset.tenant_org_id = user.tenant_org_id
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return _asset_dict(asset)


# --- Documents ---
@router.get("/{prop_id}/units/{unit_id}/documents")
def list_unit_documents(prop_id: int, unit_id: int, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    docs = db.query(Document).filter(Document.owner_entity_type == "Unit", Document.owner_entity_id == unit_id).all()
    return {"total": len(docs), "items": [_doc_dict(x) for x in docs]}


@router.post("/{prop_id}/units/{unit_id}/documents", status_code=201)
async def upload_unit_document(prop_id: int, unit_id: int, file: UploadFile = File(...), db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    from app.config import get_settings
    settings = get_settings()
    
    upload_path = os.path.join(settings.UPLOAD_DIR, f"prop_{prop_id}", f"unit_{unit_id}")
    os.makedirs(upload_path, exist_ok=True)
    
    file_path = os.path.join(upload_path, file.filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    doc = Document(
        tenant_org_id=user.tenant_org_id,
        owner_entity_type="Unit",
        owner_entity_id=unit_id,
        file_name=file.filename,
        file_path=file_path.replace("\\", "/"),
        mime_type=file.content_type,
        upload_date=datetime.now()
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return _doc_dict(doc)


def _doc_dict(d):
    return {c.name: getattr(d, c.name) for c in d.__table__.columns}


# --- Tenants ---
tenants_router = APIRouter(
    prefix="/api/tenants",
    tags=["Tenants"],
    dependencies=[Depends(require_permissions(["tenants", "leases", "portfolio"]))],
)


@tenants_router.get("")
def list_tenants(search: Optional[str] = None, skip: int = 0, limit: int = 50,
                 db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    q = db.query(Tenant).filter(Tenant.is_deleted == False)
    # Multi-tenant isolation
    if user.tenant_org_id:
        q = q.filter(Tenant.tenant_org_id == user.tenant_org_id)
    if search:
        q = q.filter(or_(Tenant.first_name.ilike(f"%{search}%"), Tenant.last_name.ilike(f"%{search}%"),
                         Tenant.email.ilike(f"%{search}%"), Tenant.tenant_code.ilike(f"%{search}%")))
    total = q.count()
    items = q.offset(skip).limit(limit).all()
    return {"total": total, "items": [_tenant_dict(t) for t in items]}


@tenants_router.post("", status_code=201)
def create_tenant(data: dict, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    tenant = Tenant(**{k: v for k, v in data.items() if hasattr(Tenant, k)})
    db.add(tenant)
    db.commit()
    db.refresh(tenant)
    return _tenant_dict(tenant)


@tenants_router.get("/{tenant_id}")
def get_tenant(tenant_id: int, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    t = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not t:
        raise HTTPException(404, "Tenant not found")
    return _tenant_dict(t)


@tenants_router.put("/{tenant_id}")
def update_tenant(tenant_id: int, data: dict, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    t = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not t:
        raise HTTPException(404, "Tenant not found")
    for k, v in data.items():
        if hasattr(t, k) and k not in ("id", "created_at"):
            setattr(t, k, v)
    db.commit()
    db.refresh(t)
    return _tenant_dict(t)


@tenants_router.delete("/{tenant_id}")
def delete_tenant(tenant_id: int, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    t = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not t:
        raise HTTPException(404, "Tenant not found")
    t.is_deleted = True
    db.commit()
    return {"message": "Tenant deleted"}


# --- Owners ---
owners_router = APIRouter(
    prefix="/api/owners",
    tags=["Owners"],
    dependencies=[Depends(require_permissions(["owners", "portfolio"]))],
)


@owners_router.get("")
def list_owners(db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    q = db.query(Owner).filter(Owner.is_deleted == False)
    if user.tenant_org_id:
        q = q.filter(Owner.tenant_org_id == user.tenant_org_id)
    items = q.all()
    return {"total": len(items), "items": [_owner_dict(o) for o in items]}


@owners_router.post("", status_code=201)
def create_owner(data: dict, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    owner = Owner(**{k: v for k, v in data.items() if hasattr(Owner, k)})
    db.add(owner)
    db.commit()
    db.refresh(owner)
    return _owner_dict(owner)


@owners_router.get("/{owner_id}")
def get_owner(owner_id: int, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    o = db.query(Owner).filter(Owner.id == owner_id, Owner.is_deleted == False).first()
    if not o:
        raise HTTPException(404, "Owner not found")
    return _owner_dict(o)


@owners_router.put("/{owner_id}")
def update_owner(owner_id: int, data: dict, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    o = db.query(Owner).filter(Owner.id == owner_id).first()
    if not o:
        raise HTTPException(404, "Owner not found")
    for k, v in data.items():
        if hasattr(o, k) and k not in ("id", "created_at"):
            setattr(o, k, v)
    db.commit()
    db.refresh(o)
    return _owner_dict(o)


@owners_router.delete("/{owner_id}")
def delete_owner(owner_id: int, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    o = db.query(Owner).filter(Owner.id == owner_id).first()
    if not o:
        raise HTTPException(404, "Owner not found")
    o.is_deleted = True
    db.commit()
    return {"message": "Owner deleted"}


# --- Vendors ---
vendors_router = APIRouter(
    prefix="/api/vendors",
    tags=["Vendors"],
    dependencies=[Depends(require_permissions(["vendors", "maintenance", "work_orders"]))],
)


@vendors_router.get("")
def list_vendors(db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    q = db.query(Vendor).filter(Vendor.is_deleted == False)
    if user.tenant_org_id:
        q = q.filter(Vendor.tenant_org_id == user.tenant_org_id)
    items = q.all()
    return {"total": len(items), "items": [_v_dict(v) for v in items]}


@vendors_router.post("", status_code=201)
def create_vendor(data: dict, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    vendor = Vendor(**{k: v for k, v in data.items() if hasattr(Vendor, k)})
    db.add(vendor)
    db.commit()
    db.refresh(vendor)
    return _v_dict(vendor)


@vendors_router.get("/{vendor_id}")
def get_vendor(vendor_id: int, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    v = db.query(Vendor).filter(Vendor.id == vendor_id, Vendor.is_deleted == False).first()
    if not v:
        raise HTTPException(404, "Vendor not found")
    return _v_dict(v)


@vendors_router.put("/{vendor_id}")
def update_vendor(vendor_id: int, data: dict, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    v = db.query(Vendor).filter(Vendor.id == vendor_id).first()
    if not v:
        raise HTTPException(404, "Vendor not found")
    for k, v_val in data.items():
        if hasattr(v, k) and k not in ("id", "created_at"):
            setattr(v, k, v_val)
    db.commit()
    db.refresh(v)
    return _v_dict(v)


@vendors_router.delete("/{vendor_id}")
def delete_vendor(vendor_id: int, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    v = db.query(Vendor).filter(Vendor.id == vendor_id).first()
    if not v:
        raise HTTPException(404, "Vendor not found")
    v.is_deleted = True
    db.commit()
    return {"message": "Vendor deleted"}


# --- Regions ---
@router.get("/regions")
def list_regions(db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    items = db.query(Region).all()
    return {"total": len(items), "items": [{c.name: getattr(r, c.name) for c in r.__table__.columns} for r in items]}


@router.post("/regions", status_code=201)
def create_region(data: dict, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    region = Region(**{k: v for k, v in data.items() if hasattr(Region, k)})
    db.add(region)
    db.commit()
    db.refresh(region)
    return {c.name: getattr(region, c.name) for c in region.__table__.columns}


# --- Helpers ---
def _prop_dict(p):
    return {c.name: getattr(p, c.name) for c in p.__table__.columns}

def _unit_dict(u):
    return {c.name: getattr(u, c.name) for c in u.__table__.columns}

def _bldg_dict(b):
    return {c.name: getattr(b, c.name) for c in b.__table__.columns}

def _floor_dict(f):
    return {c.name: getattr(f, c.name) for c in f.__table__.columns}

def _asset_dict(a):
    return {c.name: getattr(a, c.name) for c in a.__table__.columns}

def _tenant_dict(t):
    return {c.name: getattr(t, c.name) for c in t.__table__.columns}

def _owner_dict(o):
    return {c.name: getattr(o, c.name) for c in o.__table__.columns}

def _v_dict(v):
    return {c.name: getattr(v, c.name) for c in v.__table__.columns}

def _org_dict(o):
    return {c.name: getattr(o, c.name) for c in o.__table__.columns}
