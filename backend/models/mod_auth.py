from enum import Enum
from pydantic import BaseModel, EmailStr
from typing import Optional

class UserRole(str, Enum):
    USER = "user"
    TRAINER = "trainer"
    ADMIN = "admin"

class AuthUser(BaseModel):
    id: str
    email: EmailStr
    name: str
    role: UserRole = UserRole.USER

class TokenData(BaseModel):
    id: str
    email: EmailStr
    name: str
    role: UserRole = UserRole.USER
    exp: Optional[float] = None
    original_token: Optional[str] = None  # Campo para guardar el token original