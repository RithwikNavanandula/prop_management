"""Standalone Asset Management API routes."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import Optional
from datetime import datetime
from app.database import get_db
from app.auth.dependencies import get_current_user
from app.auth.models import UserAccount
from app.modules.properties.models import Asset

router = APIRouter(prefix="/api/assets", tags=["Assets"])


def _asset_dict(a):
    d = {c.name: getattr(a, c.name) for c in a.__table__.columns}
    d["is_allocated"] = a.unit_id is not None
    return d


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
    asset = Asset(**{k: v for k, v in data.items() if hasattr(Asset, k)})
    if not asset.asset_number:
        # Auto-generate asset number
        count = db.query(Asset).count()
        asset.asset_number = f"AST-{count + 1:05d}"
    if asset.unit_id:
        asset.allocated_at = datetime.now()
    if user.tenant_org_id:
        asset.tenant_org_id = user.tenant_org_id
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return _asset_dict(asset)


@router.put("/{asset_id}")
def update_asset(asset_id: int, data: dict, db: Session = Depends(get_db), user: UserAccount = Depends(get_current_user)):
    asset = db.query(Asset).filter(Asset.id == asset_id).first()
    if not asset:
        raise HTTPException(404, "Asset not found")
    for k, v in data.items():
        if hasattr(asset, k) and k not in ("id", "created_at"):
            setattr(asset, k, v)
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
