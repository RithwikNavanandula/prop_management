"""Auth dependencies – JWT token validation, role checks."""
import logging
from datetime import datetime, timedelta
from typing import Optional, List
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from app.database import get_db
from app.config import get_settings
from app.auth.models import UserAccount, Role

logger = logging.getLogger(__name__)
settings = get_settings()
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
security = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


async def get_current_user_from_token(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db),
) -> Optional[UserAccount]:
    if getattr(request.state, "_current_user_loaded", False):
        return getattr(request.state, "_current_user", None)

    token = None
    if credentials:
        token = credentials.credentials
    if not token:
        token = request.cookies.get("access_token")
        logger.debug("Cookie token: %s", "present" if token else "absent")

    if not token:
        logger.debug("No token found in headers or cookies")
        request.state._current_user = None
        request.state._current_user_loaded = True
        return None
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id = payload.get("sub")
        logger.debug("Token payload user_id: %s", user_id)
        if user_id is None:
            request.state._current_user = None
            request.state._current_user_loaded = True
            return None
    except JWTError as e:
        logger.debug("JWT Error: %s", e)
        request.state._current_user = None
        request.state._current_user_loaded = True
        return None

    try:
        user_id_int = int(user_id)
    except (ValueError, TypeError):
        request.state._current_user = None
        request.state._current_user_loaded = True
        return None
    user = db.query(UserAccount).filter(UserAccount.id == user_id_int, UserAccount.is_active == True).first()
    logger.debug("User found: %s", user.username if user else None)
    request.state._current_user = user
    request.state._current_user_loaded = True
    return user


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db),
) -> UserAccount:
    user = await get_current_user_from_token(request, credentials, db)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return user


def require_roles(allowed_roles: List[str]):
    async def role_checker(
        request: Request,
        credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
        db: Session = Depends(get_db),
    ):
        user = await get_current_user(request, credentials, db)
        role = _get_current_role(request, db, user.role_id)
        if not role or role.role_name not in allowed_roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return user
    return role_checker


def _normalize_permissions(perms) -> dict:
    if perms is None:
        return {}
    if isinstance(perms, dict):
        return perms
    if isinstance(perms, list):
        return {p: True for p in perms if isinstance(p, str)}
    return {}


def _has_permission(perms: dict, required: str) -> bool:
    if perms.get(required) is True:
        return True
    if ":" in required:
        base = required.split(":", 1)[0]
        if perms.get(base) is True:
            return True
    if "." in required:
        base = required.split(".", 1)[0]
        if perms.get(base) is True:
            return True
    return False


def require_permissions(required: List[str] | str):
    if isinstance(required, str):
        required_list = [required]
    else:
        required_list = list(required)

    async def permission_checker(
        request: Request,
        credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
        db: Session = Depends(get_db),
    ):
        user = await get_current_user(request, credentials, db)
        role = _get_current_role(request, db, user.role_id)
        if not role:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        perms = _normalize_permissions(role.permissions)
        if role.role_name == "admin" or perms.get("all") is True:
            return user
        for req in required_list:
            if _has_permission(perms, req):
                return user
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

    return permission_checker


def _get_current_role(request: Request, db: Session, role_id: int) -> Optional[Role]:
    cached_role = getattr(request.state, "_current_role", None)
    if cached_role and cached_role.id == role_id:
        return cached_role
    role = db.query(Role).filter(Role.id == role_id, Role.is_active == True).first()
    request.state._current_role = role
    return role
