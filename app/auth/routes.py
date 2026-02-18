"""Auth API routes – login, register, user management."""
from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from datetime import datetime
from typing import Any
from app.database import get_db
from app.auth.models import UserAccount, Role
from app.auth.schemas import LoginRequest, TokenResponse, UserCreate, UserResponse, UserUpdate
from app.modules.properties.models import TenantOrg, Tenant, Owner, Vendor, StaffUser
from app.auth.dependencies import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user,
    get_current_user_from_token,
    require_permissions,
)

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        value = str(value)
    value = value.strip()
    return value or None


def _resolve_tenant_org_id(req: UserCreate, current_user: UserAccount | None, db: Session) -> int:
    if req.tenant_org_id is not None:
        if (
            current_user
            and current_user.role_id != 1
            and current_user.tenant_org_id
            and req.tenant_org_id != current_user.tenant_org_id
        ):
            raise HTTPException(status_code=403, detail="Cross-org account creation denied")
        return req.tenant_org_id

    if current_user and current_user.tenant_org_id:
        return current_user.tenant_org_id

    org = db.query(TenantOrg).order_by(TenantOrg.id.asc()).first()
    if not org:
        raise HTTPException(status_code=422, detail="No tenant organization configured")
    return org.id


@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest, response: Response, db: Session = Depends(get_db)):
    user = db.query(UserAccount).filter(UserAccount.username == req.username).first()
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account disabled")
    user.last_login_at = datetime.utcnow()
    db.commit()
    role = db.query(Role).filter(Role.id == user.role_id).first()
    token = create_access_token({"sub": str(user.id), "role": role.role_name if role else "viewer"})
    response.set_cookie("access_token", token, httponly=True, max_age=28800, samesite="lax")
    return TokenResponse(
        access_token=token,
        user=UserResponse(
            id=user.id, username=user.username, email=user.email,
            full_name=user.full_name, role_id=user.role_id,
            role_name=role.role_name if role else None,
            linked_entity_type=user.linked_entity_type,
            is_active=user.is_active, last_login_at=user.last_login_at,
            avatar_url=user.avatar_url,
        ),
    )


@router.post("/register", response_model=UserResponse, status_code=201)
def register(
    req: UserCreate,
    db: Session = Depends(get_db),
    current_user: UserAccount | None = Depends(get_current_user_from_token),
):
    # Allow open registration only for initial bootstrap.
    if db.query(UserAccount).count() > 0 and (not current_user or current_user.role_id != 1):
        raise HTTPException(status_code=403, detail="Forbidden: Admin access required")
    if db.query(UserAccount).filter((UserAccount.username == req.username) | (UserAccount.email == req.email)).first():
        raise HTTPException(status_code=409, detail="Username or email already exists")

    role = db.query(Role).filter(Role.id == req.role_id, Role.is_active == True).first()
    if not role:
        raise HTTPException(status_code=422, detail="Invalid or inactive role")

    if req.profile is not None and not isinstance(req.profile, dict):
        raise HTTPException(status_code=422, detail="profile must be an object")
    profile = req.profile or {}

    tenant_org_id = _resolve_tenant_org_id(req, current_user, db)
    role_name = (role.role_name or "").lower()

    linked_entity_type = req.linked_entity_type
    linked_entity_id = req.linked_entity_id
    full_name = _clean_text(req.full_name)

    try:
        if role_name == "tenant":
            if linked_entity_type and linked_entity_type != "Tenant":
                raise HTTPException(status_code=422, detail="tenant role must link to Tenant")
            if linked_entity_id:
                tenant = db.query(Tenant).filter(Tenant.id == linked_entity_id, Tenant.is_deleted == False).first()
                if not tenant:
                    raise HTTPException(status_code=404, detail="Linked tenant not found")
                if tenant_org_id and tenant.tenant_org_id != tenant_org_id:
                    raise HTTPException(status_code=403, detail="Cross-org tenant link denied")
            else:
                tenant_code = _clean_text(profile.get("tenant_code"))
                first_name = _clean_text(profile.get("first_name"))
                if not tenant_code or not first_name:
                    raise HTTPException(status_code=422, detail="Tenant profile requires tenant_code and first_name")
                existing = db.query(Tenant).filter(
                    Tenant.tenant_org_id == tenant_org_id,
                    Tenant.tenant_code == tenant_code,
                    Tenant.is_deleted == False,
                ).first()
                if existing:
                    raise HTTPException(status_code=409, detail="Tenant code already exists")
                tenant = Tenant(
                    tenant_org_id=tenant_org_id,
                    tenant_code=tenant_code,
                    tenant_type=_clean_text(profile.get("tenant_type")) or "Individual",
                    first_name=first_name,
                    last_name=_clean_text(profile.get("last_name")),
                    company_name=_clean_text(profile.get("company_name")),
                    email=_clean_text(profile.get("email")) or req.email,
                    phone=_clean_text(profile.get("phone")),
                    id_type=_clean_text(profile.get("id_type")),
                    id_number=_clean_text(profile.get("id_number")),
                    status="Active",
                )
                db.add(tenant)
                db.flush()
                linked_entity_id = tenant.id
            linked_entity_type = "Tenant"
            if not full_name:
                full_name = " ".join(part for part in [_clean_text(profile.get("first_name")), _clean_text(profile.get("last_name"))] if part) or "Tenant User"

        elif role_name == "owner":
            if linked_entity_type and linked_entity_type != "Owner":
                raise HTTPException(status_code=422, detail="owner role must link to Owner")
            if linked_entity_id:
                owner = db.query(Owner).filter(Owner.id == linked_entity_id, Owner.is_deleted == False).first()
                if not owner:
                    raise HTTPException(status_code=404, detail="Linked owner not found")
                if tenant_org_id and owner.tenant_org_id != tenant_org_id:
                    raise HTTPException(status_code=403, detail="Cross-org owner link denied")
            else:
                owner_code = _clean_text(profile.get("owner_code"))
                owner_type_raw = (_clean_text(profile.get("owner_type")) or "Individual").lower()
                owner_type = "Corporate" if owner_type_raw == "corporate" else "Individual"
                first_name = _clean_text(profile.get("first_name"))
                last_name = _clean_text(profile.get("last_name"))
                company_name = _clean_text(profile.get("company_name"))
                if not owner_code:
                    raise HTTPException(status_code=422, detail="Owner profile requires owner_code")
                if owner_type == "Corporate" and not company_name:
                    raise HTTPException(status_code=422, detail="Corporate owner requires company_name")
                if owner_type != "Corporate" and not first_name:
                    raise HTTPException(status_code=422, detail="Individual owner requires first_name")
                existing = db.query(Owner).filter(
                    Owner.tenant_org_id == tenant_org_id,
                    Owner.owner_code == owner_code,
                    Owner.is_deleted == False,
                ).first()
                if existing:
                    raise HTTPException(status_code=409, detail="Owner code already exists")
                owner = Owner(
                    tenant_org_id=tenant_org_id,
                    owner_code=owner_code,
                    owner_type=owner_type,
                    first_name=first_name,
                    last_name=last_name,
                    company_name=company_name,
                    email=_clean_text(profile.get("email")) or req.email,
                    phone=_clean_text(profile.get("phone")),
                    tax_id=_clean_text(profile.get("tax_id")),
                    status="Active",
                )
                db.add(owner)
                db.flush()
                linked_entity_id = owner.id
            linked_entity_type = "Owner"
            if not full_name:
                full_name = _clean_text(profile.get("company_name")) or " ".join(
                    part for part in [_clean_text(profile.get("first_name")), _clean_text(profile.get("last_name"))] if part
                ) or "Owner User"

        elif role_name == "vendor":
            if linked_entity_type and linked_entity_type != "Vendor":
                raise HTTPException(status_code=422, detail="vendor role must link to Vendor")
            if linked_entity_id:
                vendor = db.query(Vendor).filter(Vendor.id == linked_entity_id, Vendor.is_deleted == False).first()
                if not vendor:
                    raise HTTPException(status_code=404, detail="Linked vendor not found")
                if tenant_org_id and vendor.tenant_org_id != tenant_org_id:
                    raise HTTPException(status_code=403, detail="Cross-org vendor link denied")
            else:
                vendor_code = _clean_text(profile.get("vendor_code"))
                company_name = _clean_text(profile.get("company_name"))
                if not vendor_code or not company_name:
                    raise HTTPException(status_code=422, detail="Vendor profile requires vendor_code and company_name")
                existing = db.query(Vendor).filter(
                    Vendor.tenant_org_id == tenant_org_id,
                    Vendor.vendor_code == vendor_code,
                    Vendor.is_deleted == False,
                ).first()
                if existing:
                    raise HTTPException(status_code=409, detail="Vendor code already exists")
                vendor = Vendor(
                    tenant_org_id=tenant_org_id,
                    vendor_code=vendor_code,
                    company_name=company_name,
                    contact_person=_clean_text(profile.get("contact_person")),
                    email=_clean_text(profile.get("email")) or req.email,
                    phone=_clean_text(profile.get("phone")),
                    service_category=_clean_text(profile.get("service_category")),
                    license_number=_clean_text(profile.get("license_number")),
                    status="Active",
                )
                db.add(vendor)
                db.flush()
                linked_entity_id = vendor.id
            linked_entity_type = "Vendor"
            if not full_name:
                full_name = _clean_text(profile.get("company_name")) or "Vendor User"

        elif role_name in {"admin", "manager", "accountant", "support"}:
            if linked_entity_type and linked_entity_type != "Staff":
                raise HTTPException(status_code=422, detail=f"{role_name} role must link to Staff")
            if linked_entity_id:
                staff = db.query(StaffUser).filter(StaffUser.id == linked_entity_id).first()
                if not staff:
                    raise HTTPException(status_code=404, detail="Linked staff profile not found")
                if tenant_org_id and staff.tenant_org_id != tenant_org_id:
                    raise HTTPException(status_code=403, detail="Cross-org staff link denied")
            else:
                employee_code = _clean_text(profile.get("employee_code"))
                first_name = _clean_text(profile.get("first_name"))
                if not employee_code or not first_name:
                    raise HTTPException(status_code=422, detail="Staff profile requires employee_code and first_name")
                existing = db.query(StaffUser).filter(
                    StaffUser.tenant_org_id == tenant_org_id,
                    StaffUser.employee_code == employee_code,
                ).first()
                if existing:
                    raise HTTPException(status_code=409, detail="Employee code already exists")
                staff = StaffUser(
                    tenant_org_id=tenant_org_id,
                    employee_code=employee_code,
                    first_name=first_name,
                    last_name=_clean_text(profile.get("last_name")),
                    email=_clean_text(profile.get("email")) or req.email,
                    phone=_clean_text(profile.get("phone")),
                    role_id=req.role_id,
                    department=_clean_text(profile.get("department")),
                    status="Active",
                )
                db.add(staff)
                db.flush()
                linked_entity_id = staff.id
            linked_entity_type = "Staff"
            if not full_name:
                full_name = " ".join(part for part in [_clean_text(profile.get("first_name")), _clean_text(profile.get("last_name"))] if part) or "Staff User"

        user = UserAccount(
            username=req.username,
            email=req.email,
            password_hash=hash_password(req.password),
            full_name=full_name,
            role_id=req.role_id,
            tenant_org_id=tenant_org_id,
            linked_entity_type=linked_entity_type,
            linked_entity_id=linked_entity_id,
        )
        db.add(user)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=f"Registration failed: {exc.orig}") from exc

    db.refresh(user)
    return UserResponse(
        id=user.id, username=user.username, email=user.email,
        full_name=user.full_name, role_id=user.role_id,
        role_name=role.role_name if role else None,
        linked_entity_type=user.linked_entity_type,
        is_active=user.is_active, last_login_at=user.last_login_at,
        avatar_url=user.avatar_url,
    )


@router.get("/me", response_model=UserResponse)
def get_me(user: UserAccount = Depends(get_current_user), db: Session = Depends(get_db)):
    role = db.query(Role).filter(Role.id == user.role_id).first()
    return UserResponse(
        id=user.id, username=user.username, email=user.email,
        full_name=user.full_name, role_id=user.role_id,
        role_name=role.role_name if role else None,
        linked_entity_type=user.linked_entity_type,
        is_active=user.is_active, last_login_at=user.last_login_at,
        avatar_url=user.avatar_url,
    )


@router.post("/logout")
def logout_post(response: Response):
    response.delete_cookie("access_token")
    return {"message": "Logged out"}


@router.get("/logout")
def logout_get(response: Response):
    response.delete_cookie("access_token")
    return RedirectResponse(url="/login", status_code=302)


@router.get("/users", response_model=list[UserResponse])
def list_users(
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(require_permissions(["admin", "users"])),
):
    users = db.query(UserAccount).all()
    results = []
    for user in users:
        role = db.query(Role).filter(Role.id == user.role_id).first()
        results.append(UserResponse(
            id=user.id, username=user.username, email=user.email,
            full_name=user.full_name, role_id=user.role_id,
            role_name=role.role_name if role else None,
            linked_entity_type=user.linked_entity_type,
            is_active=user.is_active, last_login_at=user.last_login_at,
            avatar_url=user.avatar_url,
        ))
    return results


@router.put("/users/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    req: UserUpdate,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(require_permissions(["admin", "users"])),
):
    user = db.query(UserAccount).filter(UserAccount.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    update_data = req.model_dump(exclude_unset=True)
    if "username" in update_data and update_data["username"] != user.username:
        username_exists = db.query(UserAccount).filter(
            UserAccount.username == update_data["username"],
            UserAccount.id != user.id,
        ).first()
        if username_exists:
            raise HTTPException(status_code=409, detail="Username already exists")
    if "email" in update_data and update_data["email"] != user.email:
        email_exists = db.query(UserAccount).filter(
            UserAccount.email == update_data["email"],
            UserAccount.id != user.id,
        ).first()
        if email_exists:
            raise HTTPException(status_code=409, detail="Email already exists")
    if "role_id" in update_data and update_data["role_id"] != user.role_id:
        raise HTTPException(
            status_code=422,
            detail="Changing role on existing users is blocked to preserve role-linked records. Create a new user instead.",
        )
    for key, value in update_data.items():
        setattr(user, key, value)
    
    db.commit()
    db.refresh(user)
    role = db.query(Role).filter(Role.id == user.role_id).first()
    return UserResponse(
        id=user.id, username=user.username, email=user.email,
        full_name=user.full_name, role_id=user.role_id,
        role_name=role.role_name if role else None,
        linked_entity_type=user.linked_entity_type,
        is_active=user.is_active, last_login_at=user.last_login_at,
        avatar_url=user.avatar_url,
    )


@router.delete("/users/{user_id}")
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(require_permissions(["admin", "users"])),
):
    user = db.query(UserAccount).filter(UserAccount.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.username == "admin":
        raise HTTPException(status_code=400, detail="Cannot delete system admin")
    db.delete(user)
    db.commit()
    return {"message": "User deleted"}


@router.get("/roles")
def list_roles(
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(require_permissions(["admin", "users", "system"])),
):
    roles = db.query(Role).all()
    return [{"id": r.id, "role_name": r.role_name, "description": r.description,
             "permissions": r.permissions, "is_system": r.is_system, "is_active": r.is_active} for r in roles]


@router.put("/roles/{role_id}")
def update_role(
    role_id: int,
    data: dict,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(require_permissions(["admin", "system"])),
):
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    if "permissions" in data:
        role.permissions = data["permissions"]
    if "description" in data:
        role.description = data["description"]
    if "is_active" in data:
        role.is_active = data["is_active"]
    db.commit()
    db.refresh(role)
    return {"id": role.id, "role_name": role.role_name, "description": role.description,
            "permissions": role.permissions, "is_system": role.is_system, "is_active": role.is_active}

