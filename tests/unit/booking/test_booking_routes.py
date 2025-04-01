import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from fastapi import FastAPI, HTTPException
from datetime import datetime, timedelta, timezone

from backend.routers.rou_booking import router
from backend.services.svc_booking import BookingService
from backend.models.mod_booking import Booking, BookingChange

app = FastAPI()
app.include_router(router)

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture
def mock_booking_service():
    with patch.object(BookingService, 'create_booking') as mock_create, \
         patch.object(BookingService, 'get_booking') as mock_get, \
         patch.object(BookingService, 'get_user_future_bookings') as mock_future, \
         patch.object(BookingService, 'get_user_past_bookings') as mock_past, \
         patch.object(BookingService, 'update_booking') as mock_update, \
         patch.object(BookingService, 'cancel_booking') as mock_cancel:
        
        yield {
            'create_booking': mock_create,
            'get_booking': mock_get,
            'get_user_future_bookings': mock_future,
            'get_user_past_bookings': mock_past,
            'update_booking': mock_update,
            'cancel_booking': mock_cancel
        }

@pytest.fixture
def sample_booking():
    start_time = datetime.now(timezone.utc) + timedelta(days=1)
    end_time = start_time + timedelta(hours=1)
    return Booking(
        id="booking123",
        user_id="user123",
        trainer_id="trainer456",
        center_id="center789",
        start_time=start_time,
        end_time=end_time,
        status="booked",
        message="Test booking",
        changes=[]
    )

@pytest.fixture
def create_booking_payload():
    start_time = datetime.now(timezone.utc) + timedelta(days=1)
    end_time = start_time + timedelta(hours=1)
    return {
        "user_id": "user123",
        "trainer_id": "trainer456",
        "center_id": "center789",
        "start_time": start_time.isoformat(),
        "end_time": end_time.isoformat(),
        "message": "Test booking"
    }

def test_create_booking_success(client, mock_booking_service, sample_booking, create_booking_payload):
    # Mock auth dependency for a regular user
    with patch('backend.dependencies.dep_auth.get_current_user', return_value={"id": "user123", "type": "user"}):
        # Mock service response
        mock_booking_service['create_booking'].return_value = sample_booking
        
        # Send request
        response = client.post(
            "/bookings/",
            json=create_booking_payload
        )
        
        # Assertions
        assert response.status_code == 200
        assert response.json()["id"] == "booking123"
        assert response.json()["user_id"] == "user123"
        assert response.json()["trainer_id"] == "trainer456"
        assert mock_booking_service['create_booking'].called

def test_create_booking_different_user(client, mock_booking_service, create_booking_payload):
    # Mock auth dependency with a different user ID
    with patch('backend.dependencies.dep_auth.get_current_user', return_value={"id": "different_user", "type": "user"}):
        # Send request
        response = client.post(
            "/bookings/",
            json=create_booking_payload
        )
        
        # Assertions
        assert response.status_code == 403
        assert "You can only create bookings for yourself" in response.json()["detail"]
        assert not mock_booking_service['create_booking'].called

def test_get_booking_user_own(client, mock_booking_service, sample_booking):
    # Mock auth dependency for the booking's user
    with patch('backend.dependencies.dep_auth.get_current_user', return_value={"id": "user123", "type": "user"}):
        # Mock service response
        mock_booking_service['get_booking'].return_value = sample_booking
        
        # Send request
        response = client.get("/bookings/booking123")
        
        # Assertions
        assert response.status_code == 200
        assert response.json()["id"] == "booking123"
        assert response.json()["user_id"] == "user123"
        assert mock_booking_service['get_booking'].called

def test_get_booking_trainer_own(client, mock_booking_service, sample_booking):
    # Mock auth dependency for the booking's trainer
    with patch('backend.dependencies.dep_auth.get_current_user', return_value={"id": "trainer456", "type": "trainer"}):
        # Mock service response
        mock_booking_service['get_booking'].return_value = sample_booking
        
        # Send request
        response = client.get("/bookings/booking123")
        
        # Assertions
        assert response.status_code == 200
        assert response.json()["id"] == "booking123"
        assert response.json()["trainer_id"] == "trainer456"
        assert mock_booking_service['get_booking'].called

def test_get_booking_admin(client, mock_booking_service, sample_booking):
    # Mock auth dependency for an admin
    with patch('backend.dependencies.dep_auth.get_current_user', return_value={"id": "admin123", "type": "admin"}):
        # Mock service response
        mock_booking_service['get_booking'].return_value = sample_booking
        
        # Send request
        response = client.get("/bookings/booking123")
        
        # Assertions
        assert response.status_code == 200
        assert response.json()["id"] == "booking123"
        assert mock_booking_service['get_booking'].called

def test_get_booking_unauthorized(client, mock_booking_service, sample_booking):
    # Mock auth dependency for a different user
    with patch('backend.dependencies.dep_auth.get_current_user', return_value={"id": "different_user", "type": "user"}):
        # Mock service response
        mock_booking_service['get_booking'].return_value = sample_booking
        
        # Send request
        response = client.get("/bookings/booking123")
        
        # Assertions
        assert response.status_code == 403
        assert "don't have permission" in response.json()["detail"]
        assert mock_booking_service['get_booking'].called

def test_get_booking_not_found(client, mock_booking_service):
    # Mock auth dependency
    with patch('backend.dependencies.dep_auth.get_current_user', return_value={"id": "user123", "type": "user"}):
        # Mock service response
        mock_booking_service['get_booking'].return_value = None
        
        # Send request
        response = client.get("/bookings/nonexistent")
        
        # Assertions
        assert response.status_code == 404
        assert "not found" in response.json()["detail"]
        assert mock_booking_service['get_booking'].called

def test_get_user_future_bookings_own(client, mock_booking_service, sample_booking):
    # Mock auth dependency for the user
    with patch('backend.dependencies.dep_auth.get_current_user', return_value={"id": "user123", "type": "user"}):
        # Mock service response
        mock_booking_service['get_user_future_bookings'].return_value = [sample_booking]
        
        # Send request
        response = client.get("/bookings/users/user123/future")
        
        # Assertions
        assert response.status_code == 200
        assert isinstance(response.json(), list)
        assert len(response.json()) == 1
        assert response.json()[0]["id"] == "booking123"
        assert mock_booking_service['get_user_future_bookings'].called

def test_get_user_future_bookings_unauthorized(client, mock_booking_service):
    # Mock auth dependency for a different user
    with patch('backend.dependencies.dep_auth.get_current_user', return_value={"id": "different_user", "type": "user"}):
        # Send request
        response = client.get("/bookings/users/user123/future")
        
        # Assertions
        assert response.status_code == 403
        assert "can only view your own bookings" in response.json()["detail"]
        assert not mock_booking_service['get_user_future_bookings'].called

def test_get_user_future_bookings_admin(client, mock_booking_service, sample_booking):
    # Mock auth dependency for an admin
    with patch('backend.dependencies.dep_auth.get_current_user', return_value={"id": "admin123", "type": "admin"}):
        # Mock service response
        mock_booking_service['get_user_future_bookings'].return_value = [sample_booking]
        
        # Send request
        response = client.get("/bookings/users/user123/future")
        
        # Assertions
        assert response.status_code == 200
        assert isinstance(response.json(), list)
        assert len(response.json()) == 1
        assert response.json()[0]["id"] == "booking123"
        assert mock_booking_service['get_user_future_bookings'].called

def test_get_user_past_bookings_own(client, mock_booking_service, sample_booking):
    # Mock auth dependency for the user
    with patch('backend.dependencies.dep_auth.get_current_user', return_value={"id": "user123", "type": "user"}):
        # Mock service response
        mock_booking_service['get_user_past_bookings'].return_value = [sample_booking]
        
        # Send request
        response = client.get("/bookings/users/user123/past")
        
        # Assertions
        assert response.status_code == 200
        assert isinstance(response.json(), list)
        assert len(response.json()) == 1
        assert response.json()[0]["id"] == "booking123"
        assert mock_booking_service['get_user_past_bookings'].called

def test_get_user_past_bookings_unauthorized(client, mock_booking_service):
    # Mock auth dependency for a different user
    with patch('backend.dependencies.dep_auth.get_current_user', return_value={"id": "different_user", "type": "user"}):
        # Send request
        response = client.get("/bookings/users/user123/past")
        
        # Assertions
        assert response.status_code == 403
        assert "can only view your own bookings" in response.json()["detail"]
        assert not mock_booking_service['get_user_past_bookings'].called

def test_update_booking_user_own(client, mock_booking_service, sample_booking):
    # Mock auth dependency for the booking's user
    with patch('backend.dependencies.dep_auth.get_current_user', return_value={"id": "user123", "type": "user"}):
        # Mock service responses
        mock_booking_service['get_booking'].return_value = sample_booking
        mock_booking_service['update_booking'].return_value = sample_booking
        
        # Send request with updated data
        update_data = {
            "message": "Updated message"
        }
        response = client.put(
            "/bookings/booking123",
            json=update_data
        )
        
        # Assertions
        assert response.status_code == 200
        assert response.json()["id"] == "booking123"
        assert mock_booking_service['get_booking'].called
        assert mock_booking_service['update_booking'].called

def test_update_booking_trainer(client, mock_booking_service, sample_booking):
    # Mock auth dependency for the booking's trainer
    with patch('backend.dependencies.dep_auth.get_current_user', return_value={"id": "trainer456", "type": "trainer"}):
        # Mock service responses
        mock_booking_service['get_booking'].return_value = sample_booking
        mock_booking_service['update_booking'].return_value = sample_booking
        
        # Send request with updated data
        update_data = {
            "message": "Updated by trainer"
        }
        response = client.put(
            "/bookings/booking123",
            json=update_data
        )
        
        # Assertions
        assert response.status_code == 200
        assert response.json()["id"] == "booking123"
        assert mock_booking_service['get_booking'].called
        assert mock_booking_service['update_booking'].called

def test_update_booking_unauthorized(client, mock_booking_service, sample_booking):
    # Mock auth dependency for a different user
    with patch('backend.dependencies.dep_auth.get_current_user', return_value={"id": "different_user", "type": "user"}):
        # Mock service response
        mock_booking_service['get_booking'].return_value = sample_booking
        
        # Send request with updated data
        update_data = {
            "message": "Unauthorized update"
        }
        response = client.put(
            "/bookings/booking123",
            json=update_data
        )
        
        # Assertions
        assert response.status_code == 403
        assert "don't have permission" in response.json()["detail"]
        assert mock_booking_service['get_booking'].called
        assert not mock_booking_service['update_booking'].called

def test_cancel_booking_user_own(client, mock_booking_service, sample_booking):
    # Mock auth dependency for the booking's user
    with patch('backend.dependencies.dep_auth.get_current_user', return_value={"id": "user123", "type": "user"}):
        # Mock service responses
        mock_booking_service['get_booking'].return_value = sample_booking
        
        # Create a cancelled booking copy
        cancelled_booking = sample_booking.copy()
        cancelled_booking.status = "cancelled"
        cancelled_booking.changes = [
            BookingChange(
                timestamp=datetime.now(timezone.utc),
                change_type="cancellation"
            )
        ]
        mock_booking_service['cancel_booking'].return_value = cancelled_booking
        
        # Send request
        response = client.post("/bookings/booking123/cancel")
        
        # Assertions
        assert response.status_code == 200
        assert response.json()["id"] == "booking123"
        assert response.json()["status"] == "cancelled"
        assert mock_booking_service['get_booking'].called
        assert mock_booking_service['cancel_booking'].called

def test_cancel_booking_trainer(client, mock_booking_service, sample_booking):
    # Mock auth dependency for the booking's trainer
    with patch('backend.dependencies.dep_auth.get_current_user', return_value={"id": "trainer456", "type": "trainer"}):
        # Mock service responses
        mock_booking_service['get_booking'].return_value = sample_booking
        
        # Create a cancelled booking copy
        cancelled_booking = sample_booking.copy()
        cancelled_booking.status = "cancelled"
        cancelled_booking.changes = [
            BookingChange(
                timestamp=datetime.now(timezone.utc),
                change_type="cancellation"
            )
        ]
        mock_booking_service['cancel_booking'].return_value = cancelled_booking
        
        # Send request
        response = client.post("/bookings/booking123/cancel")
        
        # Assertions
        assert response.status_code == 200
        assert response.json()["id"] == "booking123"
        assert response.json()["status"] == "cancelled"
        assert mock_booking_service['get_booking'].called
        assert mock_booking_service['cancel_booking'].called

def test_cancel_booking_unauthorized(client, mock_booking_service, sample_booking):
    # Mock auth dependency for a different user
    with patch('backend.dependencies.dep_auth.get_current_user', return_value={"id": "different_user", "type": "user"}):
        # Mock service response
        mock_booking_service['get_booking'].return_value = sample_booking
        
        # Send request
        response = client.post("/bookings/booking123/cancel")
        
        # Assertions
        assert response.status_code == 403
        assert "don't have permission" in response.json()["detail"]
        assert mock_booking_service['get_booking'].called
        assert not mock_booking_service['cancel_booking'].called

def test_cancel_booking_not_found(client, mock_booking_service):
    # Mock auth dependency
    with patch('backend.dependencies.dep_auth.get_current_user', return_value={"id": "user123", "type": "user"}):
        # Mock service response
        mock_booking_service['get_booking'].return_value = None
        
        # Send request
        response = client.post("/bookings/nonexistent/cancel")
        
        # Assertions
        assert response.status_code == 404
        assert "not found" in response.json()["detail"]
        assert mock_booking_service['get_booking'].called
        assert not mock_booking_service['cancel_booking'].called