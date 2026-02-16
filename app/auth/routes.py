"""Auth API routes – login, register, user management."""
from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from datetime import datetime
from app.database import get_db
from app.auth.models import UserAccount, Role
from app.auth.schemas import LoginRequest, TokenResponse, UserCreate, UserResponse, UserUpdate
from app.auth.dependencies import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user,
    get_current_user_from_token,
    require_permissions,
)

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


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
    user = UserAccount(
        username=req.username, email=req.email,
        password_hash=hash_password(req.password),
        full_name=req.full_name, role_id=req.role_id,
        linked_entity_type=req.linked_entity_type,
        linked_entity_id=req.linked_entity_id,
    )
    db.add(user)
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
    return [{"id": r.id, "role_name": r.role_name, "description": r.description, "permissions": r.permissions} for r in roles]
