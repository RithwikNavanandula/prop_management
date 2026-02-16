"""Pydantic schemas for authentication."""
from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime


class LoginRequest(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserResponse"

class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str
    full_name: Optional[str] = None
    role_id: int = 2
    linked_entity_type: Optional[str] = None
    linked_entity_id: Optional[int] = None

class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    full_name: Optional[str]
    role_id: int
    role_name: Optional[str] = None
    linked_entity_type: Optional[str]
    is_active: bool
    last_login_at: Optional[datetime]
    avatar_url: Optional[str]
    class Config:
        from_attributes = True

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    role_id: Optional[int] = None
    is_active: Optional[bool] = None
    avatar_url: Optional[str] = None
