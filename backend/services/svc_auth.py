from azure.cosmos import ContainerProxy
import httpx
import requests
import asyncio
from backend.configuration.config import Config
from backend.schemas.sch_auth import (
    UserRegistrationRequest, 
    LoginRequest, 
    TokenResponse, 
    UserProfile,
    VerifyOTPRequest,
    SubmitOTPRequest,
    RegisterResponse,
    UserInfo,
    UpdateUserProfileRequest
)
from backend.models.mod_auth import AuthTokenData, AuthUser
from fastapi import HTTPException
import json
from typing import Optional, Dict, Any
from jose import jwt
from backend.configuration.monitor import log_event, log_exception, start_span

class AuthError:
    """Helper class to process Microsoft Entra ID API errors"""
    
    # Error categories
    INVALID_REQUEST = "invalid_request"
    INVALID_GRANT = "invalid_grant"
    EXPIRED_TOKEN = "expired_token"
    ATTRIBUTES_REQUIRED = "attributes_required"
    UNAUTHORIZED_CLIENT = "unauthorized_client"
    UNSUPPORTED_CHALLENGE_TYPE = "unsupported_challenge_type"
    USER_NOT_FOUND = "user_not_found"
    INVALID_CLIENT = "invalid_client"
    
    # Suberror codes for invalid_grant
    PASSWORD_TOO_WEAK = "password_too_weak"
    PASSWORD_TOO_SHORT = "password_too_short"
    PASSWORD_TOO_LONG = "password_too_long"
    PASSWORD_RECENTLY_USED = "password_recently_used"
    PASSWORD_BANNED = "password_banned"
    PASSWORD_IS_INVALID = "password_is_invalid"
    INVALID_OOB_VALUE = "invalid_oob_value"
    ATTRIBUTE_VALIDATION_FAILED = "attribute_validation_failed"
    
    # Suberror codes for invalid_client
    NATIVEAUTHAPI_DISABLED = "nativeauthapi_disabled"
    
    # User-friendly error messages
    ERROR_MESSAGES = {
        # Main errors
        INVALID_REQUEST: "Invalid request parameters",
        INVALID_GRANT: "Authentication failed",
        EXPIRED_TOKEN: "Your session has expired, please try again",
        ATTRIBUTES_REQUIRED: "Additional information is required",
        UNAUTHORIZED_CLIENT: "Application is not authorized",
        UNSUPPORTED_CHALLENGE_TYPE: "Authentication method not supported",
        USER_NOT_FOUND: "User account not found",
        INVALID_CLIENT: "Application configuration error",
        
        # Suberrors
        PASSWORD_TOO_WEAK: "Password is too weak and doesn't meet complexity requirements",
        PASSWORD_TOO_SHORT: "Password must be at least 8 characters long",
        PASSWORD_TOO_LONG: "Password exceeds the maximum length of 256 characters",
        PASSWORD_RECENTLY_USED: "Password has been used recently, please choose a different one",
        PASSWORD_BANNED: "Password contains banned words or patterns",
        PASSWORD_IS_INVALID: "Password contains invalid characters",
        INVALID_OOB_VALUE: "The verification code is incorrect",
        ATTRIBUTE_VALIDATION_FAILED: "Some of the provided information is invalid",
        NATIVEAUTHAPI_DISABLED: "Native authentication is not enabled for this application"
    }
    
    @staticmethod
    def process_error(response_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process an error response from Microsoft Entra ID API
        
        Args:
            response_data: The JSON error response from Microsoft Entra ID
            
        Returns:
            A structured error object with user-friendly messages
        """
        error = response_data.get("error")
        suberror = response_data.get("suberror")
        error_description = response_data.get("error_description", "Unknown error")
        error_codes = response_data.get("error_codes", [])
        
        # Create structured error response
        error_obj = {
            "code": error,
            "message": AuthError.ERROR_MESSAGES.get(error, "Authentication error occurred"),
            "description": error_description,
            "details": response_data
        }
        
        # Add suberror information if available
        if suberror:
            error_obj["suberror"] = {
                "code": suberror,
                "message": AuthError.ERROR_MESSAGES.get(suberror, "Additional authentication error")
            }
        
        return error_obj
    
    @staticmethod
    def raise_http_exception(response_data: Dict[str, Any], context: str = "") -> None:
        """
        Process an error and raise an HTTPException with structured error details
        
        Args:
            response_data: The JSON error response from Microsoft Entra ID
            context: Additional context about where the error occurred
            
        Raises:
            HTTPException with structured error details
        """
        error_obj = AuthError.process_error(response_data)
        
        if context:
            error_obj["context"] = context
        
        # Determine appropriate status code
        status_code = 400  # Default to 400 Bad Request
        error = response_data.get("error")
        
        if error == AuthError.USER_NOT_FOUND:
            status_code = 404
        elif error == AuthError.UNAUTHORIZED_CLIENT or error == AuthError.INVALID_CLIENT:
            status_code = 401
        elif error == AuthError.EXPIRED_TOKEN:
            status_code = 401
            
        raise HTTPException(status_code=status_code, detail=error_obj)

class AuthService:
    @staticmethod
    async def register_user(db: ContainerProxy, registration: UserRegistrationRequest) -> RegisterResponse:
        try:
            # Start operation span for registration
            with start_span("register_user", attributes={"email": registration.email}):
                log_event("User registration started", {"email": registration.email})
                
                # Step 1: Start registration flow
                start_url = f"https://{Config.AZURE_ENTRAID_TENANT_SUBDOMAIN}.ciamlogin.com/{Config.AZURE_ENTRAID_TENANT_SUBDOMAIN}.onmicrosoft.com/signup/v1.0/start"

                attributes = {
                    "displayName": f"{registration.givenName} {registration.surname}",
                    "postalCode": registration.postalCode,
                    "streetAddress": registration.streetAddress,
                    "city": registration.city,
                    f"{Config.AZURE_ENTRAID_B2C_EXTENSIONS}_cusBirthday": registration.cusBirthday,
                    f"{Config.AZURE_ENTRAID_B2C_EXTENSIONS}_cusPhone": registration.cusPhone,
                    f"{Config.AZURE_ENTRAID_B2C_EXTENSIONS}_cusRole": "user",  # Set role to 'user' by default,
                    "surname": registration.surname,
                    "givenName": registration.givenName,
                }

                start_payload = {
                    'client_id': Config.AZURE_ENTRAID_CLIENT_ID,
                    'challenge_type': 'oob password redirect',
                    'attributes': json.dumps(attributes),
                    'username': registration.email
                }

                async with httpx.AsyncClient() as client:
                    start_response = await client.post(start_url, data=start_payload)
                    if start_response.status_code != 200:
                        AuthError.raise_http_exception(start_response.json(), context="register_user - Step 1")
                    continuation_token = start_response.json().get("continuation_token")

                # Step 2: Select authentication method (send OTP code)
                challenge_url = f"https://{Config.AZURE_ENTRAID_TENANT_SUBDOMAIN}.ciamlogin.com/{Config.AZURE_ENTRAID_TENANT_SUBDOMAIN}.onmicrosoft.com/signup/v1.0/challenge"
                challenge_payload = {
                    'client_id': Config.AZURE_ENTRAID_CLIENT_ID,
                    'challenge_type': 'oob password redirect',
                    'continuation_token': continuation_token
                }

                async with httpx.AsyncClient() as client:
                    challenge_response = await client.post(challenge_url, data=challenge_payload)
                    if challenge_response.status_code != 200:
                        AuthError.raise_http_exception(challenge_response.json(), context="register_user - Step 2")

                log_event("User registration OTP sent", {"email": registration.email})
                return RegisterResponse(
                    message="OTP code has been sent to your email. Enter the code in the next step.",
                    continuation_token=continuation_token
                )
        except Exception as e:
            log_exception(e, {"email": registration.email, "operation": "register_user"})
            raise

    @staticmethod
    async def verify_otp(request: VerifyOTPRequest) -> TokenResponse:
        try:
            with start_span("verify_otp", attributes={"email": request.email}):
                log_event("OTP verification started", {"email": request.email})
                
                if not request.password or not request.email:
                    raise HTTPException(status_code=400, detail="Missing 'password' or 'email' parameter")

                continue_url = f"https://{Config.AZURE_ENTRAID_TENANT_SUBDOMAIN}.ciamlogin.com/{Config.AZURE_ENTRAID_TENANT_SUBDOMAIN}.onmicrosoft.com/signup/v1.0/continue"

                # Step 1: Verify OTP
                otp_payload = {
                    'client_id': Config.AZURE_ENTRAID_CLIENT_ID,
                    'continuation_token': request.continuation_token,
                    'grant_type': 'oob',
                    'oob': request.otp
                }

                async with httpx.AsyncClient() as client:
                    otp_response = await client.post(continue_url, data=otp_payload)
                    otp_json = otp_response.json()

                    if otp_response.status_code != 200:
                        if otp_json.get("error") == "credential_required":
                            continuation_token = otp_json.get("continuation_token")
                        else:
                            AuthError.raise_http_exception(otp_json, context="verify_otp - Step 1")
                    else:
                        continuation_token = otp_json.get("continuation_token")

                if not continuation_token:
                    raise HTTPException(status_code=400, detail="No continuation_token received after OTP verification")

                # Step 2: Send password
                password_payload = {
                    'client_id': Config.AZURE_ENTRAID_CLIENT_ID,
                    'continuation_token': continuation_token,
                    'grant_type': 'password',
                    'password': request.password
                }

                async with httpx.AsyncClient() as client:
                    password_response = await client.post(continue_url, data=password_payload)
                    password_json = password_response.json()
                    
                    if password_response.status_code != 200:
                        suberror = password_json.get("suberror")

                        # Special handling for password validation errors
                        if suberror in [
                            AuthError.PASSWORD_TOO_WEAK,
                            AuthError.PASSWORD_TOO_SHORT,
                            AuthError.PASSWORD_TOO_LONG,
                            AuthError.PASSWORD_RECENTLY_USED,
                            AuthError.PASSWORD_BANNED,
                            AuthError.PASSWORD_IS_INVALID
                        ]:
                            raise HTTPException(status_code=400, detail={
                                "code": suberror,
                                "message": AuthError.ERROR_MESSAGES.get(suberror, "Password validation failed"),
                                "description": password_json.get("error_description"),
                                "action": "restart_registration", 
                                "details": password_json
                            })

                        # Otherwise, raise a generic error
                        AuthError.raise_http_exception(password_json, context="verify_otp - Step 2")
                    
                    # Successfully processed password, get continuation token
                    continuation_token = password_json.get("continuation_token")

                if not continuation_token:
                    raise HTTPException(status_code=400, detail="No continuation_token received after sending password")

                # Step 3: Get final token
                token_url = f"https://{Config.AZURE_ENTRAID_TENANT_SUBDOMAIN}.ciamlogin.com/{Config.AZURE_ENTRAID_TENANT_SUBDOMAIN}.onmicrosoft.com/oauth2/v2.0/token"
                token_payload = {
                    'client_id': Config.AZURE_ENTRAID_CLIENT_ID,
                    'continuation_token': continuation_token,
                    'grant_type': 'continuation_token',
                    'username': request.email,
                    'scope': Config.AZURE_ENTRAID_SCOPE
                }

                async with httpx.AsyncClient() as client:
                    token_response = await client.post(token_url, data=token_payload)
                    if token_response.status_code != 200:
                        AuthError.raise_http_exception(token_response.json(), context="verify_otp - Step 3")
                
                log_event("OTP verification completed", {"email": request.email})
                return TokenResponse(**token_response.json())
        except Exception as e:
            log_exception(e, {"email": request.email, "operation": "verify_otp"})
            raise

    @staticmethod
    async def login(request: LoginRequest) -> TokenResponse:
        try:
            with start_span("login", attributes={"email": request.email}):
                log_event("User login started", {"email": request.email})
                
                if not request.email or not request.password:
                    raise HTTPException(status_code=400, detail="Missing email or password")

                # Step 1: Initialize login with /initiate
                initiate_url = f"https://{Config.AZURE_ENTRAID_TENANT_SUBDOMAIN}.ciamlogin.com/{Config.AZURE_ENTRAID_TENANT_SUBDOMAIN}.onmicrosoft.com/oauth2/v2.0/initiate"
                initiate_payload = {
                    'client_id': Config.AZURE_ENTRAID_CLIENT_ID,
                    'challenge_type': 'password redirect',
                    'username': request.email
                }

                async with httpx.AsyncClient() as client:
                    initiate_response = await client.post(initiate_url, data=initiate_payload)
                    if initiate_response.status_code != 200:
                        AuthError.raise_http_exception(initiate_response.json(), context="/initiate")
                    continuation_token = initiate_response.json().get("continuation_token")

                if not continuation_token:
                    raise HTTPException(status_code=400, detail="No continuation_token received in /initiate")

                # Step 2: Select authentication method with /challenge
                challenge_url = f"https://{Config.AZURE_ENTRAID_TENANT_SUBDOMAIN}.ciamlogin.com/{Config.AZURE_ENTRAID_TENANT_SUBDOMAIN}.onmicrosoft.com/oauth2/v2.0/challenge"
                challenge_payload = {
                    'client_id': Config.AZURE_ENTRAID_CLIENT_ID,
                    'challenge_type': 'password redirect',
                    'continuation_token': continuation_token
                }

                async with httpx.AsyncClient() as client:
                    challenge_response = await client.post(challenge_url, data=challenge_payload)
                    if challenge_response.status_code != 200:
                        AuthError.raise_http_exception(challenge_response.json(), context="/challenge")
                    challenge_data = challenge_response.json()

                if challenge_data.get("challenge_type") != "password":
                    raise HTTPException(status_code=400, detail={
                        "error": "Flow requires interactive authentication (redirect)",
                        "details": challenge_data
                    })

                continuation_token = challenge_data.get("continuation_token")
                if not continuation_token:
                    raise HTTPException(status_code=400, detail="No continuation_token received in /challenge")

                # Step 3: Request tokens with /token endpoint
                token_url = f"https://{Config.AZURE_ENTRAID_TENANT_SUBDOMAIN}.ciamlogin.com/{Config.AZURE_ENTRAID_TENANT_SUBDOMAIN}.onmicrosoft.com/oauth2/v2.0/token"
                token_payload = {
                    'client_id': Config.AZURE_ENTRAID_CLIENT_ID,
                    'continuation_token': continuation_token,
                    'grant_type': 'password',
                    'password': request.password,
                    'scope': Config.AZURE_ENTRAID_SCOPE
                }

                async with httpx.AsyncClient() as client:
                    token_response = await client.post(token_url, data=token_payload)
                    if token_response.status_code != 200:
                        AuthError.raise_http_exception(token_response.json(), context="/token")
                
                log_event("User login successful", {"email": request.email})
                return TokenResponse(**token_response.json())
        except Exception as e:
            log_exception(e, {"email": request.email, "operation": "login"})
            raise

    @staticmethod
    async def logout(user: AuthUser) -> dict:
        """
        Logout user by invalidating their token
        
        Args:
            user: The authenticated user object
            
        Returns:
            A success message
        """
        # For now, we just return success as token invalidation 
        # would be handled on the client side and by token expiration
        with start_span("logout", attributes={"user_id": user.id}):
            log_event("User logout", {"user_id": user.id, "email": user.email})
            return {"message": "Successfully logged out"}

    @staticmethod
    async def submit_otp(request: SubmitOTPRequest) -> dict:
        """
        Submit OTP code for verification
        """
        url = f"https://{Config.AZURE_ENTRAID_TENANT_SUBDOMAIN}.ciamlogin.com/{Config.AZURE_ENTRAID_TENANT_ID}/signup/v1.0/continue"
        payload = {
            'continuation_token': request.continuation_token,
            'client_id': Config.AZURE_ENTRAID_CLIENT_ID,
            'grant_type': 'oob',
            'oob': request.otp_code
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url, 
                data=payload, 
                headers={'Content-Type': 'application/x-www-form-urlencoded'}
            )

            if response.status_code == 200:
                return {"message": "OTP verified successfully"}
            elif response.status_code == 400:
                error_response = response.json()
                AuthError.raise_http_exception(error_response, context="submit_otp")
            
            raise HTTPException(status_code=response.status_code, detail="Failed to submit OTP")

    @staticmethod
    async def initiate_password_reset(email: str) -> dict:
        """
        Initiate the password reset process by sending a reset token to the user's email.
        """
        reset_url = f"https://{Config.AZURE_ENTRAID_TENANT_SUBDOMAIN}.ciamlogin.com/{Config.AZURE_ENTRAID_TENANT_SUBDOMAIN}.onmicrosoft.com/resetpassword/v1.0/start"
        payload = {
            'client_id': Config.AZURE_ENTRAID_CLIENT_ID,
            'challenge_type': 'oob redirect',
            'username': email
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(reset_url, data=payload)
            if response.status_code != 200:
                AuthError.raise_http_exception(response.json(), context="password_reset_initiate")
                
            # Check for redirect challenge type (which requires browser flow)
            response_data = response.json()
            if response_data.get("challenge_type") == "redirect":
                raise HTTPException(status_code=400, detail={
                    "code": "redirect_required",
                    "message": "Password reset requires browser-based flow",
                    "details": response_data
                })
                
            # Get continuation token and proceed to challenge
            continuation_token = response_data.get("continuation_token")
            
            # Send OTP challenge
            challenge_url = f"https://{Config.AZURE_ENTRAID_TENANT_SUBDOMAIN}.ciamlogin.com/{Config.AZURE_ENTRAID_TENANT_SUBDOMAIN}.onmicrosoft.com/resetpassword/v1.0/challenge"
            challenge_payload = {
                'client_id': Config.AZURE_ENTRAID_CLIENT_ID,
                'challenge_type': 'oob redirect',
                'continuation_token': continuation_token
            }
            
            challenge_response = await client.post(challenge_url, data=challenge_payload)
            if challenge_response.status_code != 200:
                AuthError.raise_http_exception(challenge_response.json(), context="password_reset_challenge")
            
            challenge_data = challenge_response.json()
            if challenge_data.get("challenge_type") == "redirect":
                raise HTTPException(status_code=400, detail={
                    "code": "redirect_required",
                    "message": "Password reset requires browser-based flow",
                    "details": challenge_data
                })

        return {
            "message": "Password reset verification code sent to email",
            "continuation_token": continuation_token,
            "challenge_type": challenge_data.get("challenge_type"),
            "code_length": challenge_data.get("code_length")
        }

    @staticmethod
    async def verify_password_reset(email: str, otp: str, new_password: str, continuation_token: str) -> dict:
        """
        Verify the OTP and set a new password
        """
        # Step 1: Verify OTP code
        continue_url = f"https://{Config.AZURE_ENTRAID_TENANT_SUBDOMAIN}.ciamlogin.com/{Config.AZURE_ENTRAID_TENANT_SUBDOMAIN}.onmicrosoft.com/resetpassword/v1.0/continue"
        continue_payload = {
            'client_id': Config.AZURE_ENTRAID_CLIENT_ID,
            'continuation_token': continuation_token,
            'grant_type': 'oob',
            'oob': otp
        }

        async with httpx.AsyncClient() as client:
            continue_response = await client.post(continue_url, data=continue_payload)
            if continue_response.status_code != 200:
                AuthError.raise_http_exception(continue_response.json(), context="password_reset_verify_otp")
                
            continue_data = continue_response.json()
            new_token = continue_data.get("continuation_token")
            
            # Step 2: Submit new password
            submit_url = f"https://{Config.AZURE_ENTRAID_TENANT_SUBDOMAIN}.ciamlogin.com/{Config.AZURE_ENTRAID_TENANT_SUBDOMAIN}.onmicrosoft.com/resetpassword/v1.0/submit"
            submit_payload = {
                'client_id': Config.AZURE_ENTRAID_CLIENT_ID,
                'continuation_token': new_token,
                'new_password': new_password
            }
            
            submit_response = await client.post(submit_url, data=submit_payload)
            if submit_response.status_code != 200:
                AuthError.raise_http_exception(submit_response.json(), context="password_reset_submit_password")
                
            submit_data = submit_response.json()
            final_token = submit_data.get("continuation_token")
            poll_interval = submit_data.get("poll_interval", 2)
            
            # Step 3: Poll for completion
            poll_url = f"https://{Config.AZURE_ENTRAID_TENANT_SUBDOMAIN}.ciamlogin.com/{Config.AZURE_ENTRAID_TENANT_SUBDOMAIN}.onmicrosoft.com/resetpassword/v1.0/poll_completion"
            poll_payload = {
                'client_id': Config.AZURE_ENTRAID_CLIENT_ID,
                'continuation_token': final_token
            }
            
            # Simple polling with a few attempts
            max_attempts = 3
            attempts = 0
            password_reset_status = None
            
            while attempts < max_attempts:
                # Wait for the recommended poll interval
                await asyncio.sleep(poll_interval)
                
                poll_response = await client.post(poll_url, data=poll_payload)
                if poll_response.status_code != 200:
                    AuthError.raise_http_exception(poll_response.json(), context="password_reset_poll")
                
                poll_data = poll_response.json()
                status = poll_data.get("status")
                
                if status == "succeeded":
                    password_reset_status = {
                        "status": "success", 
                        "message": "Password has been reset successfully",
                        "continuation_token": poll_data.get("continuation_token")
                    }
                    break
                elif status == "failed":
                    raise HTTPException(status_code=400, detail={
                        "code": "password_reset_failed",
                        "message": "Password reset failed",
                        "details": poll_data
                    })
                
                attempts += 1
            
            if not password_reset_status:
                raise HTTPException(status_code=400, detail={
                    "code": "password_reset_timeout",
                    "message": "Password reset is taking longer than expected. Please try again."
                })
            
            return password_reset_status
        
    @staticmethod
    async def get_user_info(token_data: AuthTokenData) -> UserInfo:
        """
        Extract user information from token data
        
        Args:
            token_data: The decoded token data
            
        Returns:
            User information from the token
        """
        # Extract basic data
        user_info = UserInfo(
            id=token_data.id,
            email=token_data.email,
            name=token_data.name,
            role=token_data.role,
            token_expires_at=token_data.exp  # Add the token expiration timestamp
        )
        
        # Try to extract additional information from the token without verification
        try:
            # Custom claims might be in the ID token, which is typically found in the same request
            # Here we extract the payload without verification to access all fields
            unverified_headers = jwt.get_unverified_headers(token_data.original_token)
            unverified_claims = jwt.get_unverified_claims(token_data.original_token)
            
            # Extract additional information if available
            user_info.given_name = unverified_claims.get("given_name")
            user_info.family_name = unverified_claims.get("family_name")
            
            # Custom fields from Microsoft Entra ID
            user_info.phone = unverified_claims.get("userPhone")
            user_info.birthday = unverified_claims.get("userBirthday")
            user_info.street_address = unverified_claims.get("userStreetAddress")
            
            # You can add more custom fields as needed
        except Exception:
            # If we can't extract additional information, just continue with basic info
            pass
            
        return user_info
        
    @staticmethod
    async def refresh_token(refresh_token: str) -> TokenResponse:
        """
        Refresh an access token using a refresh token
        
        Args:
            refresh_token: The refresh token from a previous authentication
            
        Returns:
            A new token response with fresh access and refresh tokens
            
        Raises:
            HTTPException: If the refresh token is invalid or expired
        """
        token_url = f"https://{Config.AZURE_ENTRAID_TENANT_SUBDOMAIN}.ciamlogin.com/{Config.AZURE_ENTRAID_TENANT_SUBDOMAIN}.onmicrosoft.com/oauth2/v2.0/token"
        
        refresh_payload = {
            'client_id': Config.AZURE_ENTRAID_CLIENT_ID,
            'refresh_token': refresh_token,
            'grant_type': 'refresh_token',
            'scope': Config.AZURE_ENTRAID_SCOPE
        }
        
        async with httpx.AsyncClient() as client:
            token_response = await client.post(token_url, data=refresh_payload)
            
            if token_response.status_code != 200:
                AuthError.raise_http_exception(token_response.json(), context="refresh_token")
            
            return TokenResponse(**token_response.json())

    @staticmethod
    async def update_user_profile(token_data: AuthTokenData, profile_data: UpdateUserProfileRequest) -> UserInfo:
        """
        Update user profile information in Microsoft Entra ID
        
        This method updates the user's profile information stored in Entra ID or Azure AD
        
        Args:
            token_data: The decoded token data of the authenticated user
            profile_data: The profile information to update
            
        Returns:
            Updated user information with the changes reflected
            
        Raises:
            HTTPException: If the update operation fails
        """
        try:
            with start_span("update_user_profile", attributes={"user_id": token_data.id}):
                log_event("User profile update started", {"user_id": token_data.id, "email": token_data.email})
                
                # Extract token claims to determine token source
                unverified_claims = jwt.get_unverified_claims(token_data.original_token)
                issuer = unverified_claims.get("iss", "")
                
                # Detect which type of token we're dealing with
                is_azure_ad = "sts.windows.net" in issuer
                
                # Step 1: Prepare the user attributes to update
                # Map the fields from the request to the appropriate attributes
                attributes = {}
                
                if profile_data.given_name:
                    attributes["givenName"] = profile_data.given_name
                
                if profile_data.family_name:
                    attributes["surname"] = profile_data.family_name
                
                if profile_data.street_address:
                    attributes["streetAddress"] = profile_data.street_address
                
                if profile_data.city:
                    attributes["city"] = profile_data.city
                
                if profile_data.postal_code:
                    attributes["postalCode"] = profile_data.postal_code
                
                # For custom extension attributes
                extension_prefix = Config.AZURE_ENTRAID_B2C_EXTENSIONS
                if profile_data.phone:
                    if is_azure_ad:
                        attributes["mobilePhone"] = profile_data.phone
                    else:
                        attributes[f"{extension_prefix}_cusPhone"] = profile_data.phone
                
                if profile_data.birthday:
                    if is_azure_ad:
                        # Azure AD doesn't have a birthday field, so we'll use an extension attribute
                        # or you might need to store this in your own database
                        pass
                    else:
                        attributes[f"{extension_prefix}_cusBirthday"] = profile_data.birthday
                
                if profile_data.preferred_language:
                    attributes["preferredLanguage"] = profile_data.preferred_language
                
                # Skip update if no attributes to change
                if not attributes:
                    raise HTTPException(status_code=400, detail={
                        "code": "invalid_request",
                        "message": "No profile information provided to update"
                    })
                
                # Step 2: Determine which API to use based on token type
                if is_azure_ad:
                    # For Azure AD tokens, use Microsoft Graph API
                    # First, get an access token for Microsoft Graph
                    token_url = f"https://login.microsoftonline.com/{unverified_claims.get('tid')}/oauth2/v2.0/token"
                    token_payload = {
                        'client_id': Config.AZURE_ENTRAID_CLIENT_ID,
                        'client_secret': Config.AZURE_ENTRAID_SECRET,
                        'scope': 'https://graph.microsoft.com/.default',
                        'grant_type': 'client_credentials'
                    }
                    
                    async with httpx.AsyncClient() as client:
                        token_response = await client.post(token_url, data=token_payload)
                        if token_response.status_code != 200:
                            raise HTTPException(status_code=500, detail={
                                "code": "graph_token_error",
                                "message": "Failed to obtain access token for Microsoft Graph API"
                            })
                        
                        graph_token = token_response.json().get('access_token')
                        
                        # Now update the user profile with Microsoft Graph API
                        graph_url = f"https://graph.microsoft.com/v1.0/users/{token_data.id}"
                        headers = {
                            'Authorization': f'Bearer {graph_token}',
                            'Content-Type': 'application/json'
                        }
                        
                        update_response = await client.patch(graph_url, json=attributes, headers=headers)
                        
                        if update_response.status_code >= 400:
                            # Handle error
                            try:
                                error_data = update_response.json()
                                error_message = error_data.get("error", {}).get("message", "Unknown error")
                                
                                raise HTTPException(status_code=update_response.status_code, detail={
                                    "code": "profile_update_error",
                                    "message": f"Failed to update profile: {error_message}"
                                })
                            except (json.JSONDecodeError, KeyError):
                                raise HTTPException(status_code=500, detail={
                                    "code": "update_error",
                                    "message": f"Unknown error updating profile: {update_response.status_code}"
                                })
                else:
                    # For Entra External ID tokens, use usermanagement API
                    update_url = f"https://{Config.AZURE_ENTRAID_TENANT_SUBDOMAIN}.ciamlogin.com/{Config.AZURE_ENTRAID_TENANT_SUBDOMAIN}.onmicrosoft.com/usermanagement/v1.0/users/{token_data.id}"
                    headers = {
                        'Authorization': f'Bearer {token_data.original_token}',
                        'Content-Type': 'application/json'
                    }
                    
                    async with httpx.AsyncClient() as client:
                        update_response = await client.patch(update_url, json=attributes, headers=headers)
                        
                        if update_response.status_code >= 400:
                            # Handle error
                            try:
                                error_data = update_response.json()
                                error_message = error_data.get("error", {}).get("message", "Unknown error")
                                
                                raise HTTPException(status_code=update_response.status_code, detail={
                                    "code": "profile_update_error",
                                    "message": f"Failed to update profile: {error_message}"
                                })
                            except (json.JSONDecodeError, KeyError):
                                raise HTTPException(status_code=500, detail={
                                    "code": "update_error",
                                    "message": f"Unknown error updating profile: {update_response.status_code}"
                                })
                
                # Step 3: Return updated user information
                updated_user_info = UserInfo(
                    id=token_data.id,
                    email=token_data.email,
                    name=token_data.name,
                    role=token_data.role,
                    token_expires_at=token_data.exp,
                    # Include the updated fields
                    given_name=profile_data.given_name,
                    family_name=profile_data.family_name,
                    phone=profile_data.phone,
                    birthday=profile_data.birthday,
                    street_address=profile_data.street_address,
                    city=profile_data.city,
                    postal_code=profile_data.postal_code
                )
                
                log_event("User profile updated successfully", {"user_id": token_data.id, "email": token_data.email})
                return updated_user_info
                
        except HTTPException:
            # Re-raise HTTP exceptions to preserve the status code and detail
            raise
        except Exception as e:
            log_exception(e, {"user_id": token_data.id, "email": token_data.email, "operation": "update_user_profile"})
            raise HTTPException(status_code=500, detail={
                "code": "internal_error",
                "message": "An unexpected error occurred while updating the user profile"
            })