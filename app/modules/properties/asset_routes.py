"""Standalone Asset Management API routes."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import Optional
from datetime import datetime
from decimal import Decimal, InvalidOperation
from app.database import get_db
from app.auth.dependencies import get_current_user, require_permissions
from app.auth.models import UserAccount
from app.modules.properties.models import Asset

router = APIRouter(
    prefix="/api/assets",
    tags=["Assets"],
    dependencies=[Depends(require_permissions(["properties", "portfolio"]))],
)


def _asset_dict(a):
    d = {c.name: getattr(a, c.name) for c in a.__table__.columns}
    d["is_allocated"] = a.unit_id is not None
    return d


def _coerce_asset_value(column, value):
    if value is None:
        return None
    if isinstance(value, str):
        value = value.strip()
        if value.lower() in {"", "null", "none", "nan"}:
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

    if python_type is datetime:
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError as exc:
                raise ValueError("invalid datetime") from exc
        raise ValueError("invalid datetime")

    if python_type.__name__ == "date":
        if hasattr(value, "year") and hasattr(value, "month") and hasattr(value, "day"):
            return value
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value).date()
            except ValueError:
                try:
                    return datetime.strptime(value, "%Y-%m-%d").date()
                except ValueError as exc:
                    raise ValueError("invalid date") from exc
        raise ValueError("invalid date")

    return value


def _sanitize_asset_payload(data: dict, blocked_fields: set | None = None) -> dict:
    blocked_fields = blocked_fields or set()
    clean = {}
    errors = []
    for key, value in data.items():
        if key in blocked_fields:
            continue
        column = Asset.__table__.columns.get(key)
        if column is None:
            continue
        try:
            clean[key] = _coerce_asset_value(column, value)
        except ValueError:
            errors.append(key)
    if errors:
        raise HTTPException(status_code=422, detail=f"Invalid values for fields: {', '.join(errors)}")
    return clean


@router.get("")
def list_assets(
    search: Optional[str] = None,
    status: Optional[str] = None,
    allocated: Optional[bool] = None,
    property_id: Optional[int] = None,
    db: Session = Depends(get_db),
    user: UserAccount = Depends(get_current_user),
):
    q = db.query(Asset)
    if user.tenant_org_id:
        q = q.filter(Asset.tenant_org_id == user.tenant_org_id)
    if search:
        q = q.filter(or_(
            Asset.asset_name.ilike(f"%{search}%"),
            Asset.asset_type.ilike(f"%{search}%"),
            Asset.serial_number.ilike(f"%{search}%"),
            Asset.asset_number.ilike(f"%{search}%"),
        ))
    if status:
        q = q.filter(Asset.status == status)
    if allocated is True:
        q = q.filter(Asset.unit_id.isnot(None))
    elif allocated is False:
        q = q.filter(Asset.unit_id.is_(None))
    if property_id:
        q = q.filter(Asset.property_id == property_id)
    items = q.order_by(Asset.created_at.desc()).all()
    return {"total": len(items), "items": [_asset_dict(a) for a in items]}


@router.get("/{asset_id}")
def get_asset(asset_id: int, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    asset = db.query(Asset).filter(Asset.id == asset_id).first()
    if not asset:
        raise HTTPException(404, "Asset not found")
    return _asset_dict(asset)


@router.post("", status_code=201)
def create_asset(data: dict, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    clean_data = _sanitize_asset_payload(data, blocked_fields={"id", "created_at", "updated_at"})
    asset = Asset(**clean_data)
    if not asset.asset_number:
        # Auto-generate asset number
        count = db.query(Asset).count()
        asset.asset_number = f"AST-{count + 1:05d}"
    if asset.unit_id:
        asset.allocated_at = datetime.now()
    if user.tenant_org_id:
        asset.tenant_org_id = user.tenant_org_id
    if not asset.asset_name:
        raise HTTPException(status_code=422, detail="asset_name is required")
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return _asset_dict(asset)


@router.put("/{asset_id}")
def update_asset(asset_id: int, data: dict, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    asset = db.query(Asset).filter(Asset.id == asset_id).first()
    if not asset:
        raise HTTPException(404, "Asset not found")
    clean_data = _sanitize_asset_payload(data, blocked_fields={"id", "created_at", "updated_at", "tenant_org_id"})
    for k, v in clean_data.items():
        if hasattr(asset, k):
            setattr(asset, k, v)
    if asset.unit_id and not asset.allocated_at:
        asset.allocated_at = datetime.now()
    if not asset.unit_id:
        asset.allocated_at = None
    db.commit()
    db.refresh(asset)
    return _asset_dict(asset)


@router.delete("/{asset_id}")
def delete_asset(asset_id: int, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    asset = db.query(Asset).filter(Asset.id == asset_id).first()
    if not asset:
        raise HTTPException(404, "Asset not found")
    db.delete(asset)
    db.commit()
    return {"message": "Asset deleted"}


@router.post("/{asset_id}/allocate")
def allocate_asset(asset_id: int, data: dict, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    """Allocate an asset to a unit."""
    asset = db.query(Asset).filter(Asset.id == asset_id).first()
    if not asset:
        raise HTTPException(404, "Asset not found")
    unit_id = data.get("unit_id")
    if not unit_id:
        raise HTTPException(400, "unit_id is required")
    asset.unit_id = unit_id
    asset.property_id = data.get("property_id", asset.property_id)
    asset.allocated_at = datetime.now()
    db.commit()
    db.refresh(asset)
    return _asset_dict(asset)


@router.post("/{asset_id}/unallocate")
def unallocate_asset(asset_id: int, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    """Remove asset from its unit assignment."""
    asset = db.query(Asset).filter(Asset.id == asset_id).first()
    if not asset:
        raise HTTPException(404, "Asset not found")
    asset.unit_id = None
    asset.allocated_at = None
    db.commit()
    db.refresh(asset)
    return _asset_dict(asset)
