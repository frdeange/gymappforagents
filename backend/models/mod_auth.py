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
    Fullname: str
    name: str
    surName: str
    role: UserRole = UserRole.USER
    phone: str
    birthday: str
    city: str
    streetAddress : str    
    postalCode: str
    tokenExpiration : int
    original_token: Optional[str] = None


class AuthTokenData(BaseModel):
    id: str
    email: EmailStr
    name: str
    userGivenName: Optional[str] = None
    userLastName: Optional[str] = None
    role: UserRole = UserRole.USER
    exp: Optional[float] = None
    original_token: Optional[str] = None 