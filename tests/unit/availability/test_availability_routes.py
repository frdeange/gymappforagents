import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from fastapi import FastAPI, HTTPException

from backend.routers.rou_availability import router
from backend.services.svc_availability import AvailabilityService
from backend.models.mod_availability import Availability, RecurrenceType
from datetime import datetime, time, timezone

app = FastAPI()
app.include_router(router)

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture
def mock_availability_service():
    with patch.object(AvailabilityService, 'create_availability') as mock_create, \
         patch.object(AvailabilityService, 'get_availability') as mock_get, \
         patch.object(AvailabilityService, 'get_trainer_availabilities') as mock_get_trainer, \
         patch.object(AvailabilityService, 'get_center_availabilities') as mock_get_center, \
         patch.object(AvailabilityService, 'update_availability') as mock_update, \
         patch.object(AvailabilityService, 'delete_availability') as mock_delete:
        
        yield {
            'create_availability': mock_create,
            'get_availability': mock_get,
            'get_trainer_availabilities': mock_get_trainer,
            'get_center_availabilities': mock_get_center,
            'update_availability': mock_update,
            'delete_availability': mock_delete
        }

@pytest.fixture
def sample_availability():
    return Availability(
        id="test-id",
        trainer_id="trainer123",
        center_id="center456",
        recurrence_type=RecurrenceType.WEEKLY,
        schedule=[
            {
                "day_of_week": 1,
                "available": True,
                "time_slots": [
                    {
                        "start_time": time(9, 0),
                        "end_time": time(10, 0)
                    }
                ]
            }
        ],
        start_date=datetime(2025, 4, 1, tzinfo=timezone.utc),
        end_date=datetime(2025, 6, 30, tzinfo=timezone.utc),
        created_at=datetime(2025, 3, 31, 12, 0, 0, tzinfo=timezone.utc),
        updated_at=datetime(2025, 3, 31, 12, 0, 0, tzinfo=timezone.utc)
    )

def test_create_availability_trainer(client, mock_availability_service, sample_availability):
    # Mock the auth dependency for a trainer
    with patch('backend.dependencies.dep_auth.get_current_user', return_value={"id": "trainer123", "type": "trainer"}):
        # Setup mock return value
        mock_availability_service['create_availability'].return_value = sample_availability
        
        # Send request
        response = client.post(
            "/availabilities/",
            json={
                "trainer_id": "trainer123",
                "center_id": "center456",
                "recurrence_type": "weekly",
                "schedule": [
                    {
                        "day_of_week": 1,
                        "available": True,
                        "time_slots": [
                            {
                                "start_time": "09:00:00",
                                "end_time": "10:00:00"
                            }
                        ]
                    }
                ],
                "start_date": "2025-04-01T00:00:00Z",
                "end_date": "2025-06-30T00:00:00Z"
            }
        )
        
        # Assertions
        assert response.status_code == 200
        assert response.json()["id"] == "test-id"
        assert response.json()["trainer_id"] == "trainer123"
        assert mock_availability_service['create_availability'].called

def test_create_availability_unauthorized(client, mock_availability_service):
    # Mock the auth dependency for a regular user
    with patch('backend.dependencies.dep_auth.get_current_user', return_value={"id": "user123", "type": "user"}):
        # Send request
        response = client.post(
            "/availabilities/",
            json={
                "trainer_id": "trainer123",
                "center_id": "center456",
                "recurrence_type": "weekly",
                "schedule": [
                    {
                        "day_of_week": 1,
                        "available": True,
                        "time_slots": [
                            {
                                "start_time": "09:00:00",
                                "end_time": "10:00:00"
                            }
                        ]
                    }
                ],
                "start_date": "2025-04-01T00:00:00Z",
                "end_date": "2025-06-30T00:00:00Z"
            }
        )
        
        # Assertions
        assert response.status_code == 403
        assert "Only trainers and administrators" in response.json()["detail"]
        assert not mock_availability_service['create_availability'].called

def test_create_availability_wrong_trainer(client, mock_availability_service):
    # Mock the auth dependency for a trainer trying to create availability for another trainer
    with patch('backend.dependencies.dep_auth.get_current_user', return_value={"id": "trainer456", "type": "trainer"}):
        # Send request
        response = client.post(
            "/availabilities/",
            json={
                "trainer_id": "trainer123",
                "center_id": "center456",
                "recurrence_type": "weekly",
                "schedule": [
                    {
                        "day_of_week": 1,
                        "available": True,
                        "time_slots": [
                            {
                                "start_time": "09:00:00",
                                "end_time": "10:00:00"
                            }
                        ]
                    }
                ],
                "start_date": "2025-04-01T00:00:00Z",
                "end_date": "2025-06-30T00:00:00Z"
            }
        )
        
        # Assertions
        assert response.status_code == 403
        assert "Trainers can only create their own" in response.json()["detail"]
        assert not mock_availability_service['create_availability'].called

def test_create_availability_admin(client, mock_availability_service, sample_availability):
    # Mock the auth dependency for an admin
    with patch('backend.dependencies.dep_auth.get_current_user', return_value={"id": "admin123", "type": "admin"}):
        # Setup mock return value
        mock_availability_service['create_availability'].return_value = sample_availability
        
        # Send request
        response = client.post(
            "/availabilities/",
            json={
                "trainer_id": "trainer123",
                "center_id": "center456",
                "recurrence_type": "weekly",
                "schedule": [
                    {
                        "day_of_week": 1,
                        "available": True,
                        "time_slots": [
                            {
                                "start_time": "09:00:00",
                                "end_time": "10:00:00"
                            }
                        ]
                    }
                ],
                "start_date": "2025-04-01T00:00:00Z",
                "end_date": "2025-06-30T00:00:00Z"
            }
        )
        
        # Assertions
        assert response.status_code == 200
        assert response.json()["id"] == "test-id"
        assert mock_availability_service['create_availability'].called

def test_get_availability_found(client, mock_availability_service, sample_availability):
    # Mock the auth dependency
    with patch('backend.dependencies.dep_auth.get_current_user', return_value={"id": "user123", "type": "user"}):
        # Setup mock return value
        mock_availability_service['get_availability'].return_value = sample_availability
        
        # Send request
        response = client.get("/availabilities/test-id")
        
        # Assertions
        assert response.status_code == 200
        assert response.json()["id"] == "test-id"
        assert response.json()["trainer_id"] == "trainer123"
        assert mock_availability_service['get_availability'].called

def test_get_availability_not_found(client, mock_availability_service):
    # Mock the auth dependency
    with patch('backend.dependencies.dep_auth.get_current_user', return_value={"id": "user123", "type": "user"}):
        # Setup mock return value
        mock_availability_service['get_availability'].return_value = None
        
        # Send request
        response = client.get("/availabilities/nonexistent-id")
        
        # Assertions
        assert response.status_code == 404
        assert "not found" in response.json()["detail"]
        assert mock_availability_service['get_availability'].called

def test_get_trainer_availabilities(client, mock_availability_service, sample_availability):
    # Mock the auth dependency
    with patch('backend.dependencies.dep_auth.get_current_user', return_value={"id": "user123", "type": "user"}):
        # Setup mock return value
        mock_availability_service['get_trainer_availabilities'].return_value = [sample_availability]
        
        # Send request
        response = client.get("/availabilities/trainer/trainer123")
        
        # Assertions
        assert response.status_code == 200
        assert isinstance(response.json(), list)
        assert len(response.json()) == 1
        assert response.json()[0]["id"] == "test-id"
        assert mock_availability_service['get_trainer_availabilities'].called

def test_get_center_availabilities(client, mock_availability_service, sample_availability):
    # Mock the auth dependency
    with patch('backend.dependencies.dep_auth.get_current_user', return_value={"id": "user123", "type": "user"}):
        # Setup mock return value
        mock_availability_service['get_center_availabilities'].return_value = [sample_availability]
        
        # Send request with query parameters
        response = client.get(
            "/availabilities/center/center456?start_date=2025-04-01T00:00:00Z&end_date=2025-04-30T00:00:00Z"
        )
        
        # Assertions
        assert response.status_code == 200
        assert isinstance(response.json(), list)
        assert len(response.json()) == 1
        assert response.json()[0]["id"] == "test-id"
        assert mock_availability_service['get_center_availabilities'].called

def test_update_availability_trainer(client, mock_availability_service, sample_availability):
    # Mock the auth dependency for a trainer
    with patch('backend.dependencies.dep_auth.get_current_user', return_value={"id": "trainer123", "type": "trainer"}):
        # Setup mock return values
        mock_availability_service['get_availability'].return_value = sample_availability
        mock_availability_service['update_availability'].return_value = sample_availability
        
        # Send request
        response = client.put(
            "/availabilities/test-id",
            json={
                "end_date": "2025-05-31T00:00:00Z"
            }
        )
        
        # Assertions
        assert response.status_code == 200
        assert response.json()["id"] == "test-id"
        assert mock_availability_service['get_availability'].called
        assert mock_availability_service['update_availability'].called

def test_update_availability_not_found(client, mock_availability_service):
    # Mock the auth dependency for an admin
    with patch('backend.dependencies.dep_auth.get_current_user', return_value={"id": "admin123", "type": "admin"}):
        # Setup mock return value
        mock_availability_service['get_availability'].return_value = None
        
        # Send request
        response = client.put(
            "/availabilities/nonexistent-id",
            json={
                "end_date": "2025-05-31T00:00:00Z"
            }
        )
        
        # Assertions
        assert response.status_code == 404
        assert "not found" in response.json()["detail"]
        assert mock_availability_service['get_availability'].called
        assert not mock_availability_service['update_availability'].called

def test_update_availability_unauthorized(client, mock_availability_service, sample_availability):
    # Mock the auth dependency for a regular user
    with patch('backend.dependencies.dep_auth.get_current_user', return_value={"id": "user123", "type": "user"}):
        # Setup mock return value
        mock_availability_service['get_availability'].return_value = sample_availability
        
        # Send request
        response = client.put(
            "/availabilities/test-id",
            json={
                "end_date": "2025-05-31T00:00:00Z"
            }
        )
        
        # Assertions
        assert response.status_code == 403
        assert "permission" in response.json()["detail"]
        assert mock_availability_service['get_availability'].called
        assert not mock_availability_service['update_availability'].called

def test_delete_availability_admin(client, mock_availability_service, sample_availability):
    # Mock the auth dependency for an admin
    with patch('backend.dependencies.dep_auth.get_current_user', return_value={"id": "admin123", "type": "admin"}):
        # Setup mock return values
        mock_availability_service['get_availability'].return_value = sample_availability
        mock_availability_service['delete_availability'].return_value = True
        
        # Send request
        response = client.delete("/availabilities/test-id")
        
        # Assertions
        assert response.status_code == 204
        assert mock_availability_service['get_availability'].called
        assert mock_availability_service['delete_availability'].called

def test_delete_availability_trainer(client, mock_availability_service, sample_availability):
    # Mock the auth dependency for the trainer who owns the availability
    with patch('backend.dependencies.dep_auth.get_current_user', return_value={"id": "trainer123", "type": "trainer"}):
        # Setup mock return values
        mock_availability_service['get_availability'].return_value = sample_availability
        mock_availability_service['delete_availability'].return_value = True
        
        # Send request
        response = client.delete("/availabilities/test-id")
        
        # Assertions
        assert response.status_code == 204
        assert mock_availability_service['get_availability'].called
        assert mock_availability_service['delete_availability'].called

def test_delete_availability_unauthorized(client, mock_availability_service, sample_availability):
    # Mock the auth dependency for a trainer who doesn't own the availability
    with patch('backend.dependencies.dep_auth.get_current_user', return_value={"id": "trainer456", "type": "trainer"}):
        # Setup mock return value
        mock_availability_service['get_availability'].return_value = sample_availability
        
        # Send request
        response = client.delete("/availabilities/test-id")
        
        # Assertions
        assert response.status_code == 403
        assert "permission" in response.json()["detail"]
        assert mock_availability_service['get_availability'].called
        assert not mock_availability_service['delete_availability'].called