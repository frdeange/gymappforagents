from pydantic import BaseModel, EmailStr, Field
from typing import Optional, Dict, Any, List
from backend.models.mod_auth import UserRole

# Authentication Error Schemas
class SubErrorDetail(BaseModel):
    code: str
    message: str

class ErrorDetail(BaseModel):
    code: str
    message: str
    description: Optional[str] = None
    context: Optional[str] = None
    suberror: Optional[SubErrorDetail] = None
    details: Optional[Dict[str, Any]] = None

# Registration and Login Schemas
class UserRegistrationRequest(BaseModel):
    email: EmailStr
    password: str
    name: str
    givenName: str
    surname: str
    postalCode: Optional[str] = None
    streetAddress: Optional[str] = None
    city: Optional[str] = None
    cusBirthday: Optional[str] = None
    cusPhone: Optional[str] = None
    preferred_language: str = "es"

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class VerifyOTPRequest(BaseModel):
    email: EmailStr
    password: str
    otp: str
    continuation_token: str

class SubmitOTPRequest(BaseModel):
    otp_code: str
    continuation_token: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    id_token: str
    refresh_token: Optional[str] = None

class UserProfile(BaseModel):
    id: str
    email: EmailStr
    name: str
    role: UserRole
    preferred_language: str
    is_active: bool

class RegisterResponse(BaseModel):
    message: str
    continuation_token: str

class AdminCreateUserRequest(BaseModel):
    email: EmailStr
    password: str
    name: str
    givenName: str
    surname: str
    postalCode: Optional[str] = None
    streetAddress: Optional[str] = None
    city: Optional[str] = None
    extension_2588abcdwhtfeehjjeeqwertc_cusBirthday: Optional[str] = None
    extension_2588abcdwhtfeehjjeeqwertc_cusPhone: Optional[str] = None
    preferred_language: str = "en"
    role: UserRole

# Password Reset Schemas
class PasswordResetRequest(BaseModel):
    email: EmailStr

class PasswordResetInitiateResponse(BaseModel):
    message: str
    continuation_token: str
    challenge_type: str
    code_length: Optional[int] = None

class PasswordResetVerifyRequest(BaseModel):
    email: EmailStr
    otp: str
    new_password: str
    continuation_token: str

class PasswordResetVerifyResponse(BaseModel):
    status: str
    message: str
    continuation_token: Optional[str] = None

# User Information Schema
class UserInfo(BaseModel):
    id: str
    email: EmailStr
    name: str
    role: UserRole
    given_name: Optional[str] = None
    family_name: Optional[str] = None
    phone: Optional[str] = None
    birthday: Optional[str] = None
    street_address: Optional[str] = None
    city: Optional[str] = None
    postal_code: Optional[str] = None
    token_expires_at: Optional[float] = None  # Expiration timestamp of the current token

# Token Refresh Schemas
class RefreshTokenRequest(BaseModel):
    refresh_token: str