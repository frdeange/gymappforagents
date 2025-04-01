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
    UserInfo
)
from backend.models.mod_auth import TokenData
from fastapi import HTTPException
import json
from typing import Optional, Dict, Any
from jose import jwt

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
        """
        Start the registration process in Microsoft Entra External ID
        """
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

        return RegisterResponse(
            message="OTP code has been sent to your email. Enter the code in the next step.",
            continuation_token=continuation_token
        )

    @staticmethod
    async def verify_otp(request: VerifyOTPRequest) -> TokenResponse:
        """
        Verify OTP and complete registration process
        """
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
            if password_response.status_code != 200:
                error_details = password_response.json()
                raise HTTPException(status_code=400, detail={
                    "error": "Error sending password",
                    "suberror": error_details.get("suberror", "Not specified"),
                    "details": error_details
                })

            continuation_token = password_response.json().get("continuation_token")

        if not continuation_token:
            raise HTTPException(status_code=400, detail="No continuation_token received after sending password")

        # Step 3: Get final token
        token_url = f"https://{Config.AZURE_ENTRAID_TENANT_SUBDOMAIN}.ciamlogin.com/{Config.AZURE_ENTRAID_TENANT_SUBDOMAIN}.onmicrosoft.com/oauth2/v2.0/token"
        token_payload = {
            'client_id': Config.AZURE_ENTRAID_CLIENT_ID,
            'continuation_token': continuation_token,
            'grant_type': 'continuation_token',
            'username': request.email,
            'scope': 'openid profile email'
        }

        async with httpx.AsyncClient() as client:
            token_response = await client.post(token_url, data=token_payload)
            if token_response.status_code != 200:
                AuthError.raise_http_exception(token_response.json(), context="verify_otp - Step 3")
            
            return TokenResponse(**token_response.json())

    @staticmethod
    async def login(request: LoginRequest) -> TokenResponse:
        """
        Login a user using Microsoft Entra External ID
        """
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
            'scope': 'openid profile email offline_access'
        }

        async with httpx.AsyncClient() as client:
            token_response = await client.post(token_url, data=token_payload)
            if token_response.status_code != 200:
                AuthError.raise_http_exception(token_response.json(), context="/token")
            
            return TokenResponse(**token_response.json())

    @staticmethod
    async def logout(token: str) -> None:
        """
        Logout user by invalidating their token
        """
        # For now, we just return success as token invalidation 
        # would be handled on the client side and by token expiration
        return None

    @staticmethod
    async def get_user_profile(db: ContainerProxy, user_id: str) -> Optional[UserProfile]:
        """
        Get user profile from our database
        """
        query = f'SELECT * FROM c WHERE c.id = "{user_id}" AND c.type = "user"'
        items = list(db.query_items(query=query, enable_cross_partition_query=True))
        
        if not items:
            return None
            
        return UserProfile(**items[0])

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
    async def get_user_info(token_data: TokenData) -> UserInfo:
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
            'scope': 'openid profile email offline_access'
        }
        
        async with httpx.AsyncClient() as client:
            token_response = await client.post(token_url, data=refresh_payload)
            
            if token_response.status_code != 200:
                AuthError.raise_http_exception(token_response.json(), context="refresh_token")
            
            return TokenResponse(**token_response.json())