from fastapi import APIRouter, Depends, HTTPException, Form
from azure.cosmos import ContainerProxy
from backend.schemas.sch_auth import (
    UserRegistrationRequest,
    LoginRequest,
    TokenResponse,
    UserProfile,
    VerifyOTPRequest,
    SubmitOTPRequest,
    RegisterResponse,
    AdminCreateUserRequest,
    PasswordResetRequest,
    PasswordResetVerifyRequest,
    PasswordResetInitiateResponse,
    PasswordResetVerifyResponse,
    ErrorDetail,
    UserInfo,
    RefreshTokenRequest,
    UpdateUserProfileRequest
)
from backend.services.svc_auth import AuthService
from backend.dependencies.dep_auth import get_current_user, get_current_admin, verify_token
from backend.configuration.database import get_container
from backend.models.mod_auth import AuthUser, TokenData

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/register", response_model=RegisterResponse, responses={400: {"model": ErrorDetail}})
async def register_user(
    registration: UserRegistrationRequest,
    db: ContainerProxy = Depends(lambda: get_container("users"))
):
    """
    Register a new user. This will start the registration process and set the role to 'user' by default.
    
    Possible errors:
    - invalid_request: Invalid parameters in the request
    - user_not_found: The provided email doesn't exist
    - expired_token: The session has expired
    - attributes_required: Additional user attributes are required
    """
    return await AuthService.register_user(db, registration)

@router.post("/admin/create-user", response_model=RegisterResponse, responses={400: {"model": ErrorDetail}})
async def create_user_by_admin(
    registration: AdminCreateUserRequest,
    db: ContainerProxy = Depends(lambda: get_container("users")),
    current_admin: dict = Depends(get_current_admin)
):
    """
    Create a new user with a specific role. Only accessible to administrators.
    """
    return await AuthService.register_user(db, registration)

@router.post("/verify-otp", response_model=TokenResponse, responses={400: {"model": ErrorDetail}})
async def verify_otp(
    request: VerifyOTPRequest,
    db: ContainerProxy = Depends(lambda: get_container("users"))
):
    """
    Verify OTP code and complete the registration process
    
    Possible errors:
    - invalid_request: Invalid parameters in the request
    - invalid_grant: Authentication failed
    - invalid_oob_value: The verification code is incorrect
    - expired_token: The session has expired
    """
    return await AuthService.verify_otp(request)

@router.post("/login", response_model=TokenResponse, responses={400: {"model": ErrorDetail}, 401: {"model": ErrorDetail}})
async def login(
    request: LoginRequest,
    db: ContainerProxy = Depends(lambda: get_container("users"))
):
    """
    Login with email and password
    
    Possible errors:
    - invalid_request: Invalid parameters in the request
    - invalid_grant: Authentication failed (incorrect password)
    - user_not_found: User account not found
    - unauthorized_client: Application is not authorized
    """
    return await AuthService.login(request)

@router.post("/submit-otp", responses={400: {"model": ErrorDetail}})
async def submit_otp(request: SubmitOTPRequest):
    """
    Submit OTP code for verification
    
    Possible errors:
    - invalid_grant: Authentication failed
    - invalid_oob_value: The verification code is incorrect
    """
    return await AuthService.submit_otp(request)

@router.post("/logout")
async def logout():
    """
    Logout current user
    
    This endpoint doesn't require authentication to avoid issues with token verification.
    The actual token invalidation happens on the client side by removing tokens from storage.
    """
    return {"message": "Successfully logged out"}

@router.post("/password-reset", response_model=PasswordResetInitiateResponse, responses={400: {"model": ErrorDetail}, 404: {"model": ErrorDetail}})
async def initiate_password_reset(
    request: PasswordResetRequest
):
    """
    Initiate the password reset process by sending a verification code to the user's email.
    
    Possible errors:
    - invalid_request: Invalid parameters in the request
    - user_not_found: The provided email doesn't exist
    - redirect_required: Password reset requires browser-based flow
    """
    return await AuthService.initiate_password_reset(request.email)

@router.post("/password-reset/verify", response_model=PasswordResetVerifyResponse, responses={400: {"model": ErrorDetail}})
async def verify_password_reset(
    request: PasswordResetVerifyRequest
):
    """
    Verify the verification code and set a new password.
    
    Possible errors:
    - invalid_request: Invalid parameters in the request
    - invalid_grant: Authentication failed
    - invalid_oob_value: The verification code is incorrect
    - expired_token: The session has expired
    - password_too_weak: Password is too weak and doesn't meet complexity requirements
    - password_too_short: Password must be at least 8 characters long
    - password_too_long: Password exceeds the maximum length of 256 characters
    - password_recently_used: Password has been used recently, please choose a different one
    - password_banned: Password contains banned words or patterns
    - password_is_invalid: Password contains invalid characters
    """
    return await AuthService.verify_password_reset(
        request.email, 
        request.otp, 
        request.new_password,
        request.continuation_token
    )

@router.get("/me", response_model=UserInfo, responses={401: {"model": ErrorDetail}})
async def get_current_user_info(token: str = Depends(get_current_user)):
    """
    Get information about the currently authenticated user based on their access token.
    
    Possible errors:
    - unauthorized: Invalid or expired token
    """
    # Verify and decode the token
    token_data = await verify_token(token)
    
    # Extract user information from the token data
    return await AuthService.get_user_info(token_data)

@router.post("/refreshtoken", response_model=TokenResponse, responses={400: {"model": ErrorDetail}, 401: {"model": ErrorDetail}})
async def refresh_access_token(request: RefreshTokenRequest):
    """
    Get a new access token using a refresh token
    
    Possible errors:
    - invalid_request: Invalid parameters in the request
    - invalid_grant: Authentication failed (invalid or expired refresh token)
    """
    return await AuthService.refresh_token(request.refresh_token)

@router.post("/token", response_model=TokenResponse, tags=["Authentication"])
async def token_login(
    username: str = Form(...),
    password: str = Form(...)
):
    """
    Authenticates a user using Microsoft Entra ID CIAM.
    Accepts form data for Swagger compatibility (OAuth2 Password Flow).
    
    This endpoint is compatible with OAuth2PasswordBearer(tokenUrl="/auth/token")
    and allows direct login via Swagger UI using username and password fields.
    """
    login_request = LoginRequest(email=username, password=password)
    return await AuthService.login(login_request)