import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import json
from fastapi import HTTPException

from backend.services.svc_auth import AuthService, AuthError
from backend.schemas.sch_auth import (
    UserRegistrationRequest, 
    LoginRequest, 
    VerifyOTPRequest,
    SubmitOTPRequest,
    PasswordResetRequest,
    PasswordResetVerifyRequest
)

class TestAuthService:
    @pytest.fixture
    def mock_db(self):
        return MagicMock()
        
    @pytest.fixture
    def user_registration_data(self):
        return UserRegistrationRequest(
            email="test@example.com",
            givenName="Test",
            surname="User",
            postalCode="12345",
            streetAddress="123 Test St",
            city="Test City",
            cusBirthday="2000-01-01",
            cusPhone="+1234567890"
        )
    
    @pytest.mark.asyncio
    @patch('backend.services.svc_auth.httpx.AsyncClient')
    async def test_register_user_success(self, mock_client, mock_db, user_registration_data):
        # Setup mock responses
        mock_start_response = AsyncMock()
        mock_start_response.status_code = 200
        mock_start_response.json.return_value = {"continuation_token": "test-token"}
        
        mock_challenge_response = AsyncMock()
        mock_challenge_response.status_code = 200
        mock_challenge_response.json.return_value = {"challenge_type": "oob"}
        
        # Configure client mock
        mock_client_instance = AsyncMock()
        mock_client_instance.__aenter__.return_value.post.side_effect = [
            mock_start_response,
            mock_challenge_response
        ]
        mock_client.return_value = mock_client_instance
        
        # Call the service
        result = await AuthService.register_user(mock_db, user_registration_data)
        
        # Assertions
        assert result.message.startswith("OTP code has been sent")
        assert result.continuation_token == "test-token"
        
        # Verify client calls
        assert mock_client_instance.__aenter__.return_value.post.call_count == 2
    
    @pytest.mark.asyncio
    @patch('backend.services.svc_auth.httpx.AsyncClient')
    async def test_register_user_error(self, mock_client, mock_db, user_registration_data):
        # Setup mock error response
        mock_start_response = AsyncMock()
        mock_start_response.status_code = 400
        mock_start_response.json.return_value = {
            "error": "invalid_request",
            "error_description": "Invalid input parameters"
        }
        
        # Configure client mock
        mock_client_instance = AsyncMock()
        mock_client_instance.__aenter__.return_value.post.return_value = mock_start_response
        mock_client.return_value = mock_client_instance
        
        # Test for exception
        with pytest.raises(HTTPException) as exc_info:
            await AuthService.register_user(mock_db, user_registration_data)
        
        # Assertions
        assert exc_info.value.status_code == 400
        assert "invalid_request" in str(exc_info.value.detail)
    
    @pytest.mark.asyncio
    @patch('backend.services.svc_auth.httpx.AsyncClient')
    async def test_verify_otp_success(self, mock_client):
        # Setup mock responses for all steps
        mock_otp_response = AsyncMock()
        mock_otp_response.status_code = 200
        mock_otp_response.json.return_value = {"continuation_token": "token-2"}
        
        mock_password_response = AsyncMock()
        mock_password_response.status_code = 200
        mock_password_response.json.return_value = {"continuation_token": "token-3"}
        
        mock_token_response = AsyncMock()
        mock_token_response.status_code = 200
        mock_token_response.json.return_value = {
            "access_token": "test-access-token",
            "token_type": "Bearer",
            "expires_in": 3600,
            "id_token": "test-id-token"
        }
        
        # Configure client mock
        mock_client_instance = AsyncMock()
        mock_client_instance.__aenter__.return_value.post.side_effect = [
            mock_otp_response,
            mock_password_response,
            mock_token_response
        ]
        mock_client.return_value = mock_client_instance
        
        # Call the service
        request = VerifyOTPRequest(
            otp="123456",
            password="TestPassword123!",
            email="test@example.com",
            continuation_token="initial-token"
        )
        
        result = await AuthService.verify_otp(request)
        
        # Assertions
        assert result.access_token == "test-access-token"
        assert result.token_type == "Bearer"
        assert result.expires_in == 3600
        assert result.id_token == "test-id-token"
        
    @pytest.mark.asyncio
    @patch('backend.services.svc_auth.httpx.AsyncClient')
    async def test_login_success(self, mock_client):
        # Setup mock responses for the login steps
        mock_initiate_response = AsyncMock()
        mock_initiate_response.status_code = 200
        mock_initiate_response.json.return_value = {"continuation_token": "token-1"}
        
        mock_challenge_response = AsyncMock()
        mock_challenge_response.status_code = 200
        mock_challenge_response.json.return_value = {
            "challenge_type": "password",
            "continuation_token": "token-2"
        }
        
        mock_token_response = AsyncMock()
        mock_token_response.status_code = 200
        mock_token_response.json.return_value = {
            "access_token": "test-access-token",
            "token_type": "Bearer",
            "expires_in": 3600,
            "id_token": "test-id-token",
            "refresh_token": "test-refresh-token"
        }
        
        # Configure client mock
        mock_client_instance = AsyncMock()
        mock_client_instance.__aenter__.return_value.post.side_effect = [
            mock_initiate_response,
            mock_challenge_response,
            mock_token_response
        ]
        mock_client.return_value = mock_client_instance
        
        # Call the service
        request = LoginRequest(
            email="test@example.com",
            password="TestPassword123!"
        )
        
        result = await AuthService.login(request)
        
        # Assertions
        assert result.access_token == "test-access-token"
        assert result.token_type == "Bearer"
        assert result.refresh_token == "test-refresh-token"
    
    @pytest.mark.asyncio
    async def test_logout(self):
        # Simple test for logout (currently doesn't do much in the implementation)
        result = await AuthService.logout("test-token")
        assert result is None
    
    @pytest.mark.asyncio
    async def test_get_user_profile_found(self, mock_db):
        # Setup mock db query response
        user_data = {
            "id": "user123",
            "email": "test@example.com",
            "name": "Test User",
            "role": "user",
            "type": "user"
        }
        
        mock_db.query_items.return_value = [user_data]
        
        # Call the service
        result = await AuthService.get_user_profile(mock_db, "user123")
        
        # Assertions
        assert result is not None
        assert result.id == "user123"
        assert result.email == "test@example.com"
        assert result.name == "Test User"
        assert result.role == "user"
    
    @pytest.mark.asyncio
    async def test_get_user_profile_not_found(self, mock_db):
        # Setup mock db query empty response
        mock_db.query_items.return_value = []
        
        # Call the service
        result = await AuthService.get_user_profile(mock_db, "nonexistent")
        
        # Assertions
        assert result is None
    
    @pytest.mark.asyncio
    @patch('backend.services.svc_auth.httpx.AsyncClient')
    async def test_submit_otp_success(self, mock_client):
        # Setup mock response
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "success"}
        
        # Configure client mock
        mock_client_instance = AsyncMock()
        mock_client_instance.__aenter__.return_value.post.return_value = mock_response
        mock_client.return_value = mock_client_instance
        
        # Call the service
        request = SubmitOTPRequest(
            continuation_token="test-token",
            otp_code="123456"
        )
        
        result = await AuthService.submit_otp(request)
        
        # Assertions
        assert result["message"] == "OTP verified successfully"
    
    @pytest.mark.asyncio
    @patch('backend.services.svc_auth.httpx.AsyncClient')
    @patch('backend.services.svc_auth.asyncio.sleep')
    async def test_initiate_password_reset(self, mock_sleep, mock_client):
        # Setup mock responses
        mock_start_response = AsyncMock()
        mock_start_response.status_code = 200
        mock_start_response.json.return_value = {"continuation_token": "token-1"}
        
        mock_challenge_response = AsyncMock()
        mock_challenge_response.status_code = 200
        mock_challenge_response.json.return_value = {
            "challenge_type": "oob",
            "code_length": 6
        }
        
        # Configure client mock
        mock_client_instance = AsyncMock()
        mock_client_instance.__aenter__.return_value.post.side_effect = [
            mock_start_response,
            mock_challenge_response
        ]
        mock_client.return_value = mock_client_instance
        
        # Call the service
        result = await AuthService.initiate_password_reset("test@example.com")
        
        # Assertions
        assert "message" in result
        assert "continuation_token" in result
        assert result["challenge_type"] == "oob"
        assert result["code_length"] == 6
    
    @pytest.mark.asyncio
    @patch('backend.services.svc_auth.httpx.AsyncClient')
    @patch('backend.services.svc_auth.asyncio.sleep')
    async def test_verify_password_reset(self, mock_sleep, mock_client):
        # Setup mock responses for all steps
        mock_continue_response = AsyncMock()
        mock_continue_response.status_code = 200
        mock_continue_response.json.return_value = {"continuation_token": "token-2"}
        
        mock_submit_response = AsyncMock()
        mock_submit_response.status_code = 200
        mock_submit_response.json.return_value = {
            "continuation_token": "token-3",
            "poll_interval": 1
        }
        
        mock_poll_response = AsyncMock()
        mock_poll_response.status_code = 200
        mock_poll_response.json.return_value = {
            "status": "succeeded",
            "continuation_token": "token-4"
        }
        
        # Configure client mock
        mock_client_instance = AsyncMock()
        mock_client_instance.__aenter__.return_value.post.side_effect = [
            mock_continue_response,
            mock_submit_response,
            mock_poll_response
        ]
        mock_client.return_value = mock_client_instance
        
        # Call the service
        result = await AuthService.verify_password_reset(
            email="test@example.com",
            otp="123456",
            new_password="NewPassword123!",
            continuation_token="initial-token"
        )
        
        # Assertions
        assert result["status"] == "success"
        assert "message" in result
        assert result["continuation_token"] == "token-4"

    @pytest.mark.asyncio
    def test_auth_error_process_error(self):
        # Test error processing function
        error_data = {
            "error": "invalid_grant",
            "suberror": "password_too_weak",
            "error_description": "The password is too weak",
            "error_codes": [1001]
        }
        
        result = AuthError.process_error(error_data)
        
        # Assertions
        assert result["code"] == "invalid_grant"
        assert "message" in result
        assert result["suberror"]["code"] == "password_too_weak"
        assert "message" in result["suberror"]