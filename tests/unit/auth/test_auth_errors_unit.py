import pytest
import unittest
from unittest.mock import patch, MagicMock, AsyncMock
import json
import httpx
from fastapi.testclient import TestClient
from backend.backmain import app
from backend.services.svc_auth import AuthService, AuthError

client = TestClient(app)

class TestAuthErrorHandling(unittest.TestCase):
    """Test the authentication error handling functionality"""

    def setUp(self):
        """Setup test environment"""
        self.test_email = "test@example.com"
        self.test_password = "TestPassword123!"
        self.fake_token = "fake-token-12345"
        self.fake_otp = "123456"

    @patch("backend.services.svc_auth.httpx.AsyncClient")
    async def test_login_user_not_found(self, mock_client):
        """Test login with non-existent user"""
        # Mock the HTTP client response
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.json.return_value = {
            "error": "user_not_found",
            "error_description": "AADSTS50034: The user account does not exist",
            "error_codes": [50034],
            "timestamp": "2025-03-31 20:10:27Z",
            "correlation_id": "test-correlation-id"
        }
        
        mock_client_instance = AsyncMock()
        mock_client_instance.post.return_value = mock_response
        mock_client.return_value.__aenter__.return_value = mock_client_instance
        
        # Test error handling
        with pytest.raises(Exception) as exc_info:
            await AuthService.login({"email": self.test_email, "password": self.test_password})
        
        error = exc_info.value.detail
        assert error["code"] == "user_not_found"
        assert error["message"] == "User account not found"
        assert "context" in error
        assert "details" in error

    @patch("backend.services.svc_auth.httpx.AsyncClient")
    async def test_submit_otp_invalid_code(self, mock_client):
        """Test submission of invalid OTP code"""
        # Mock the HTTP client response
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.json.return_value = {
            "error": "invalid_grant",
            "suberror": "invalid_oob_value",
            "error_description": "AADSTS50012: Invalid OTP value",
            "error_codes": [50012],
            "timestamp": "2025-03-31 20:15:00Z",
            "correlation_id": "test-correlation-id"
        }
        
        mock_client_instance = AsyncMock()
        mock_client_instance.post.return_value = mock_response
        mock_client.return_value.__aenter__.return_value = mock_client_instance
        
        # Test error handling
        with pytest.raises(Exception) as exc_info:
            await AuthService.submit_otp({"otp_code": self.fake_otp, "continuation_token": self.fake_token})
        
        error = exc_info.value.detail
        assert error["code"] == "invalid_grant"
        assert error["message"] == "Authentication failed"
        assert "suberror" in error
        assert error["suberror"]["code"] == "invalid_oob_value"
        assert error["suberror"]["message"] == "The verification code is incorrect"

    @patch("backend.services.svc_auth.httpx.AsyncClient")
    async def test_password_reset_weak_password(self, mock_client):
        """Test password reset with weak password"""
        # Setup multiple mock responses for the password reset sequence
        mock_responses = [
            # First response: successful OTP verification
            MagicMock(status_code=200, json=MagicMock(return_value={"continuation_token": "new-token"})),
            # Second response: password too weak error
            MagicMock(status_code=400, json=MagicMock(return_value={
                "error": "invalid_grant",
                "suberror": "password_too_weak",
                "error_description": "AADSTS50008: Password does not meet complexity requirements",
                "error_codes": [50008],
                "timestamp": "2025-03-31 20:20:00Z"
            }))
        ]
        
        mock_client_instance = AsyncMock()
        mock_client_instance.post.side_effect = mock_responses
        mock_client.return_value.__aenter__.return_value = mock_client_instance
        
        # Test error handling
        with pytest.raises(Exception) as exc_info:
            await AuthService.verify_password_reset(
                self.test_email, 
                self.fake_otp, 
                "weak", 
                self.fake_token
            )
        
        error = exc_info.value.detail
        assert error["code"] == "invalid_grant"
        assert "suberror" in error
        assert error["suberror"]["code"] == "password_too_weak"
        assert error["suberror"]["message"] == "Password is too weak and doesn't meet complexity requirements"

    def test_auth_error_process_error(self):
        """Test the AuthError.process_error method"""
        # Test with main error only
        error_data = {
            "error": "invalid_request",
            "error_description": "Missing required parameter",
            "error_codes": [50000]
        }
        
        result = AuthError.process_error(error_data)
        assert result["code"] == "invalid_request"
        assert result["message"] == "Invalid request parameters"
        assert "description" in result
        assert "details" in result
        
        # Test with main error and suberror
        error_data_with_suberror = {
            "error": "invalid_grant",
            "suberror": "password_too_short",
            "error_description": "Password too short",
            "error_codes": [50005]
        }
        
        result = AuthError.process_error(error_data_with_suberror)
        assert result["code"] == "invalid_grant"
        assert result["message"] == "Authentication failed"
        assert "suberror" in result
        assert result["suberror"]["code"] == "password_too_short"
        assert result["suberror"]["message"] == "Password must be at least 8 characters long"

    def test_auth_error_raise_http_exception(self):
        """Test the AuthError.raise_http_exception method"""
        error_data = {
            "error": "user_not_found",
            "error_description": "User not found",
            "error_codes": [50034]
        }
        
        with pytest.raises(Exception) as exc_info:
            AuthError.raise_http_exception(error_data, "test_context")
        
        error = exc_info.value.detail
        assert error["code"] == "user_not_found"
        assert error["message"] == "User account not found"
        assert error["context"] == "test_context"
        assert error["details"]["error"] == "user_not_found"

if __name__ == "__main__":
    pytest.main(["-v", "test_auth_errors_unit.py"])
