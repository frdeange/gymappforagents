import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from fastapi import FastAPI, HTTPException

from backend.routers.rou_auth import router
from backend.services.svc_auth import AuthService

app = FastAPI()
app.include_router(router)

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture
def mock_auth_service():
    with patch.object(AuthService, 'register_user', new_callable=AsyncMock) as mock_register, \
         patch.object(AuthService, 'verify_otp', new_callable=AsyncMock) as mock_verify, \
         patch.object(AuthService, 'login', new_callable=AsyncMock) as mock_login, \
         patch.object(AuthService, 'logout', new_callable=AsyncMock) as mock_logout, \
         patch.object(AuthService, 'get_user_profile', new_callable=AsyncMock) as mock_profile, \
         patch.object(AuthService, 'submit_otp', new_callable=AsyncMock) as mock_submit_otp, \
         patch.object(AuthService, 'initiate_password_reset', new_callable=AsyncMock) as mock_reset, \
         patch.object(AuthService, 'verify_password_reset', new_callable=AsyncMock) as mock_verify_reset:
        
        yield {
            'register_user': mock_register,
            'verify_otp': mock_verify,
            'login': mock_login,
            'logout': mock_logout,
            'get_user_profile': mock_profile,
            'submit_otp': mock_submit_otp,
            'initiate_password_reset': mock_reset,
            'verify_password_reset': mock_verify_reset
        }

@pytest.mark.asyncio
async def test_register_user_endpoint(client, mock_auth_service):
    # Setup mock return value
    mock_auth_service['register_user'].return_value = {
        "message": "OTP code has been sent to your email. Enter the code in the next step.",
        "continuation_token": "mock-token"
    }
    
    # Send request
    response = client.post(
        "/auth/register",
        json={
            "email": "test@example.com",
            "givenName": "Test",
            "surname": "User",
            "postalCode": "12345",
            "streetAddress": "123 Test St",
            "city": "Test City",
            "cusBirthday": "2000-01-01",
            "cusPhone": "+1234567890"
        }
    )
    
    # Assertions
    assert response.status_code == 200
    assert "message" in response.json()
    assert "continuation_token" in response.json()
    assert mock_auth_service['register_user'].called

@pytest.mark.asyncio
async def test_register_user_error(client, mock_auth_service):
    # Setup mock to raise exception
    mock_auth_service['register_user'].side_effect = HTTPException(
        status_code=400,
        detail={
            "code": "invalid_request",
            "message": "Invalid input parameters"
        }
    )
    
    # Send request
    response = client.post(
        "/auth/register",
        json={
            "email": "invalid@example.com",
            "givenName": "Test",
            "surname": "User",
            "postalCode": "12345",
            "streetAddress": "123 Test St",
            "city": "Test City",
            "cusBirthday": "2000-01-01",
            "cusPhone": "+1234567890"
        }
    )
    
    # Assertions
    assert response.status_code == 400
    assert "code" in response.json()["detail"]
    assert response.json()["detail"]["code"] == "invalid_request"

@pytest.mark.asyncio
async def test_verify_otp_endpoint(client, mock_auth_service):
    # Setup mock return value
    mock_auth_service['verify_otp'].return_value = {
        "access_token": "mock-token",
        "token_type": "Bearer",
        "expires_in": 3600,
        "id_token": "mock-id-token"
    }
    
    # Send request
    response = client.post(
        "/auth/verify-otp",
        json={
            "otp": "123456",
            "password": "Password123!",
            "email": "test@example.com",
            "continuation_token": "mock-token"
        }
    )
    
    # Assertions
    assert response.status_code == 200
    assert "access_token" in response.json()
    assert "token_type" in response.json()
    assert mock_auth_service['verify_otp'].called

@pytest.mark.asyncio
async def test_login_endpoint(client, mock_auth_service):
    # Setup mock return value
    mock_auth_service['login'].return_value = {
        "access_token": "mock-token",
        "token_type": "Bearer",
        "expires_in": 3600,
        "id_token": "mock-id-token",
        "refresh_token": "mock-refresh-token"
    }
    
    # Send request
    response = client.post(
        "/auth/login",
        json={
            "email": "test@example.com",
            "password": "Password123!"
        }
    )
    
    # Assertions
    assert response.status_code == 200
    assert "access_token" in response.json()
    assert "token_type" in response.json()
    assert "refresh_token" in response.json()
    assert mock_auth_service['login'].called

@pytest.mark.asyncio
async def test_login_error(client, mock_auth_service):
    # Setup mock to raise exception
    mock_auth_service['login'].side_effect = HTTPException(
        status_code=401,
        detail={
            "code": "invalid_grant",
            "message": "The username or password is incorrect"
        }
    )
    
    # Send request
    response = client.post(
        "/auth/login",
        json={
            "email": "test@example.com",
            "password": "WrongPassword"
        }
    )
    
    # Assertions
    assert response.status_code == 401
    assert "code" in response.json()["detail"]
    assert response.json()["detail"]["code"] == "invalid_grant"

@pytest.mark.asyncio
async def test_submit_otp_endpoint(client, mock_auth_service):
    # Setup mock return value
    mock_auth_service['submit_otp'].return_value = {
        "message": "OTP verified successfully"
    }
    
    # Send request
    response = client.post(
        "/auth/submit-otp",
        json={
            "continuation_token": "mock-token",
            "otp_code": "123456"
        }
    )
    
    # Assertions
    assert response.status_code == 200
    assert "message" in response.json()
    assert mock_auth_service['submit_otp'].called

@pytest.mark.asyncio
async def test_logout_endpoint(client, mock_auth_service):
    # Setup mock return value
    mock_auth_service['logout'].return_value = None
    
    # Note: In a real test, you'd need to mock the dependencies to bypass authentication
    with patch('backend.dependencies.dep_auth.get_current_user', return_value="user123"):
        response = client.post("/auth/logout")
    
    # Assertions
    assert response.status_code == 200
    assert mock_auth_service['logout'].called

@pytest.mark.asyncio
async def test_get_profile_endpoint(client, mock_auth_service):
    # Setup mock return value
    mock_auth_service['get_user_profile'].return_value = {
        "id": "user123",
        "email": "test@example.com",
        "name": "Test User",
        "role": "user"
    }
    
    # Mock the dependency
    with patch('backend.dependencies.dep_auth.get_current_user', return_value="user123"):
        response = client.get("/auth/profile")
    
    # Assertions
    assert response.status_code == 200
    assert "id" in response.json()
    assert "email" in response.json()
    assert "name" in response.json()
    assert mock_auth_service['get_user_profile'].called

@pytest.mark.asyncio
async def test_get_profile_not_found(client, mock_auth_service):
    # Setup mock to return None
    mock_auth_service['get_user_profile'].return_value = None
    
    # Mock the dependency
    with patch('backend.dependencies.dep_auth.get_current_user', return_value="nonexistent"):
        response = client.get("/auth/profile")
    
    # Assertions
    assert response.status_code == 404

@pytest.mark.asyncio
async def test_initiate_password_reset_endpoint(client, mock_auth_service):
    # Setup mock return value
    mock_auth_service['initiate_password_reset'].return_value = {
        "message": "Password reset verification code sent to email",
        "continuation_token": "mock-token",
        "challenge_type": "oob",
        "code_length": 6
    }
    
    # Send request
    response = client.post(
        "/auth/password-reset",
        json={"email": "test@example.com"}
    )
    
    # Assertions
    assert response.status_code == 200
    assert "message" in response.json()
    assert "continuation_token" in response.json()
    assert "challenge_type" in response.json()
    assert mock_auth_service['initiate_password_reset'].called

@pytest.mark.asyncio
async def test_verify_password_reset_endpoint(client, mock_auth_service):
    # Setup mock return value
    mock_auth_service['verify_password_reset'].return_value = {
        "status": "success",
        "message": "Password has been reset successfully",
        "continuation_token": "mock-token"
    }
    
    # Send request
    response = client.post(
        "/auth/password-reset/verify",
        json={
            "email": "test@example.com",
            "otp": "123456",
            "new_password": "NewPassword123!",
            "continuation_token": "mock-token"
        }
    )
    
    # Assertions
    assert response.status_code == 200
    assert "status" in response.json()
    assert "message" in response.json()
    assert mock_auth_service['verify_password_reset'].called