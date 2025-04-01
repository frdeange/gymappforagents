import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from fastapi import FastAPI, HTTPException
from datetime import datetime, timezone

from backend.routers.rou_message import router
from backend.services.svc_message import MessageService
from backend.models.mod_message import Message, MessageType, MessageStatus, UserType
from backend.schemas.sch_message import ConversationResponse

app = FastAPI()
app.include_router(router)

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture
def mock_message_service():
    with patch.object(MessageService, 'create_individual_message') as mock_create_individual, \
         patch.object(MessageService, 'create_mass_message') as mock_create_mass, \
         patch.object(MessageService, 'get_message') as mock_get, \
         patch.object(MessageService, 'get_conversation') as mock_get_conversation, \
         patch.object(MessageService, 'get_user_conversations') as mock_get_conversations, \
         patch.object(MessageService, 'update_message') as mock_update, \
         patch.object(MessageService, 'mark_conversation_as_read') as mock_mark_read, \
         patch.object(MessageService, 'delete_message') as mock_delete:
        
        yield {
            'create_individual_message': mock_create_individual,
            'create_mass_message': mock_create_mass,
            'get_message': mock_get,
            'get_conversation': mock_get_conversation,
            'get_user_conversations': mock_get_conversations,
            'update_message': mock_update,
            'mark_conversation_as_read': mock_mark_read,
            'delete_message': mock_delete
        }

@pytest.fixture
def sample_message():
    current_time = datetime.now(timezone.utc)
    return Message(
        id="message123",
        sender_id="user456",
        sender_type=UserType.USER,
        recipient_id="trainer789",
        recipient_type=UserType.TRAINER,
        message_type=MessageType.INDIVIDUAL,
        content="Hello trainer!",
        status=MessageStatus.SENT,
        created_at=current_time,
        read_at=None,
        parent_message_id=None,
        mass_recipient_ids=None
    )

@pytest.fixture
def sample_mass_message():
    current_time = datetime.now(timezone.utc)
    return Message(
        id="massmsg123",
        sender_id="admin456",
        sender_type=UserType.ADMIN,
        recipient_id="user789",
        recipient_type=UserType.USER,
        message_type=MessageType.MASS,
        content="Announcement to all users",
        status=MessageStatus.SENT,
        created_at=current_time,
        read_at=None,
        parent_message_id=None,
        mass_recipient_ids=["user123", "user456", "user789"]
    )

def test_create_individual_message(client, mock_message_service, sample_message):
    # Mock auth dependency for a regular user
    with patch('backend.dependencies.dep_auth.get_current_user', return_value={"id": "user456", "type": "user"}):
        # Mock service response
        mock_message_service['create_individual_message'].return_value = sample_message
        
        # Send request
        response = client.post(
            "/messages/",
            json={
                "recipient_id": "trainer789",
                "recipient_type": "trainer",
                "content": "Hello trainer!",
                "parent_message_id": None
            }
        )
        
        # Assertions
        assert response.status_code == 200
        assert response.json()["id"] == "message123"
        assert response.json()["sender_id"] == "user456"
        assert response.json()["recipient_id"] == "trainer789"
        assert response.json()["content"] == "Hello trainer!"
        assert mock_message_service['create_individual_message'].called

def test_create_mass_message_as_admin(client, mock_message_service, sample_mass_message):
    # Mock auth dependency for an admin
    with patch('backend.dependencies.dep_auth.get_current_user', return_value={"id": "admin456", "type": "admin"}):
        # Mock service response
        mock_message_service['create_mass_message'].return_value = sample_mass_message
        
        # Send request
        response = client.post(
            "/messages/mass",
            json={
                "recipient_ids": ["user123", "user456", "user789"],
                "recipient_type": "user",
                "content": "Announcement to all users"
            }
        )
        
        # Assertions
        assert response.status_code == 200
        assert response.json()["id"] == "massmsg123"
        assert response.json()["sender_id"] == "admin456"
        assert response.json()["message_type"] == "mass"
        assert response.json()["content"] == "Announcement to all users"
        assert mock_message_service['create_mass_message'].called

def test_create_mass_message_unauthorized(client, mock_message_service):
    # Mock auth dependency for a regular user
    with patch('backend.dependencies.dep_auth.get_current_user', return_value={"id": "user456", "type": "user"}):
        # Send request
        response = client.post(
            "/messages/mass",
            json={
                "recipient_ids": ["user123", "user789"],
                "recipient_type": "user",
                "content": "Unauthorized mass message"
            }
        )
        
        # Assertions
        assert response.status_code == 403
        assert "Only administrators" in response.json()["detail"]
        assert not mock_message_service['create_mass_message'].called

def test_get_message_as_sender(client, mock_message_service, sample_message):
    # Mock auth dependency for the message sender
    with patch('backend.dependencies.dep_auth.get_current_user', return_value={"id": "user456", "type": "user"}):
        # Mock service response
        mock_message_service['get_message'].return_value = sample_message
        
        # Send request
        response = client.get("/messages/message123")
        
        # Assertions
        assert response.status_code == 200
        assert response.json()["id"] == "message123"
        assert response.json()["sender_id"] == "user456"
        assert response.json()["recipient_id"] == "trainer789"
        assert mock_message_service['get_message'].called

def test_get_message_as_recipient(client, mock_message_service, sample_message):
    # Mock auth dependency for the message recipient
    with patch('backend.dependencies.dep_auth.get_current_user', return_value={"id": "trainer789", "type": "trainer"}):
        # Mock service response
        mock_message_service['get_message'].return_value = sample_message
        
        # Send request
        response = client.get("/messages/message123")
        
        # Assertions
        assert response.status_code == 200
        assert response.json()["id"] == "message123"
        assert response.json()["sender_id"] == "user456"
        assert response.json()["recipient_id"] == "trainer789"
        assert mock_message_service['get_message'].called

def test_get_message_unauthorized(client, mock_message_service, sample_message):
    # Mock auth dependency for another user
    with patch('backend.dependencies.dep_auth.get_current_user', return_value={"id": "other_user", "type": "user"}):
        # Mock service response
        mock_message_service['get_message'].return_value = sample_message
        
        # Send request
        response = client.get("/messages/message123")
        
        # Assertions
        assert response.status_code == 403
        assert "not authorized" in response.json()["detail"]
        assert mock_message_service['get_message'].called

def test_get_message_as_admin(client, mock_message_service, sample_message):
    # Mock auth dependency for an admin
    with patch('backend.dependencies.dep_auth.get_current_user', return_value={"id": "admin123", "type": "admin"}):
        # Mock service response
        mock_message_service['get_message'].return_value = sample_message
        
        # Send request
        response = client.get("/messages/message123")
        
        # Assertions
        assert response.status_code == 200
        assert response.json()["id"] == "message123"
        assert response.json()["sender_id"] == "user456"
        assert response.json()["recipient_id"] == "trainer789"
        assert mock_message_service['get_message'].called

def test_get_message_not_found(client, mock_message_service):
    # Mock auth dependency
    with patch('backend.dependencies.dep_auth.get_current_user', return_value={"id": "user456", "type": "user"}):
        # Mock service response
        mock_message_service['get_message'].return_value = None
        
        # Send request
        response = client.get("/messages/nonexistent")
        
        # Assertions
        assert response.status_code == 404
        assert "not found" in response.json()["detail"]
        assert mock_message_service['get_message'].called

def test_get_conversation(client, mock_message_service, sample_message):
    # Mock auth dependency
    with patch('backend.dependencies.dep_auth.get_current_user', return_value={"id": "user456", "type": "user"}):
        # Mock service response
        conversation = ConversationResponse(
            messages=[sample_message],
            total_messages=1,
            unread_count=0
        )
        mock_message_service['get_conversation'].return_value = conversation
        
        # Send request
        response = client.get("/messages/conversation/trainer789?limit=10&offset=0")
        
        # Assertions
        assert response.status_code == 200
        assert "messages" in response.json()
        assert len(response.json()["messages"]) == 1
        assert response.json()["messages"][0]["id"] == "message123"
        assert response.json()["total_messages"] == 1
        assert response.json()["unread_count"] == 0
        assert mock_message_service['get_conversation'].called

def test_get_conversations(client, mock_message_service, sample_message):
    # Mock auth dependency
    with patch('backend.dependencies.dep_auth.get_current_user', return_value={"id": "user456", "type": "user"}):
        # Mock service response
        mock_message_service['get_user_conversations'].return_value = [sample_message]
        
        # Send request
        response = client.get("/messages/conversations")
        
        # Assertions
        assert response.status_code == 200
        assert isinstance(response.json(), list)
        assert len(response.json()) == 1
        assert response.json()[0]["id"] == "message123"
        assert response.json()[0]["sender_id"] == "user456"
        assert response.json()[0]["recipient_id"] == "trainer789"
        assert mock_message_service['get_user_conversations'].called

def test_update_message_as_recipient(client, mock_message_service, sample_message):
    # Mock auth dependency for the message recipient
    with patch('backend.dependencies.dep_auth.get_current_user', return_value={"id": "trainer789", "type": "trainer"}):
        # Mock service responses
        mock_message_service['get_message'].return_value = sample_message
        
        # Create an updated message copy
        updated_message = sample_message.copy()
        updated_message.status = MessageStatus.READ
        updated_message.read_at = datetime.now(timezone.utc)
        mock_message_service['update_message'].return_value = updated_message
        
        # Send request
        response = client.put(
            "/messages/message123",
            json={
                "status": "read",
                "read_at": datetime.now(timezone.utc).isoformat()
            }
        )
        
        # Assertions
        assert response.status_code == 200
        assert response.json()["id"] == "message123"
        assert response.json()["status"] == "read"
        assert response.json()["read_at"] is not None
        assert mock_message_service['get_message'].called
        assert mock_message_service['update_message'].called

def test_update_message_unauthorized(client, mock_message_service, sample_message):
    # Mock auth dependency for a user who is not the recipient
    with patch('backend.dependencies.dep_auth.get_current_user', return_value={"id": "other_user", "type": "user"}):
        # Mock service response
        mock_message_service['get_message'].return_value = sample_message
        
        # Send request
        response = client.put(
            "/messages/message123",
            json={
                "status": "read",
                "read_at": datetime.now(timezone.utc).isoformat()
            }
        )
        
        # Assertions
        assert response.status_code == 403
        assert "Only the recipient" in response.json()["detail"]
        assert mock_message_service['get_message'].called
        assert not mock_message_service['update_message'].called

def test_mark_conversation_as_read(client, mock_message_service, sample_message):
    # Mock auth dependency
    with patch('backend.dependencies.dep_auth.get_current_user', return_value={"id": "trainer789", "type": "trainer"}):
        # Mock service response
        updated_message = sample_message.copy()
        updated_message.status = MessageStatus.READ
        updated_message.read_at = datetime.now(timezone.utc)
        mock_message_service['mark_conversation_as_read'].return_value = [updated_message]
        
        # Send request
        response = client.post("/messages/conversation/user456/read")
        
        # Assertions
        assert response.status_code == 200
        assert isinstance(response.json(), list)
        assert len(response.json()) == 1
        assert response.json()[0]["id"] == "message123"
        assert response.json()[0]["status"] == "read"
        assert response.json()[0]["read_at"] is not None
        assert mock_message_service['mark_conversation_as_read'].called

def test_delete_message_as_sender(client, mock_message_service, sample_message):
    # Mock auth dependency for the message sender
    with patch('backend.dependencies.dep_auth.get_current_user', return_value={"id": "user456", "type": "user"}):
        # Mock service responses
        mock_message_service['get_message'].return_value = sample_message
        mock_message_service['delete_message'].return_value = True
        
        # Send request
        response = client.delete("/messages/message123")
        
        # Assertions
        assert response.status_code == 204
        assert mock_message_service['get_message'].called
        assert mock_message_service['delete_message'].called

def test_delete_message_as_admin(client, mock_message_service, sample_message):
    # Mock auth dependency for an admin
    with patch('backend.dependencies.dep_auth.get_current_user', return_value={"id": "admin123", "type": "admin"}):
        # Mock service responses
        mock_message_service['get_message'].return_value = sample_message
        mock_message_service['delete_message'].return_value = True
        
        # Send request
        response = client.delete("/messages/message123")
        
        # Assertions
        assert response.status_code == 204
        assert mock_message_service['get_message'].called
        assert mock_message_service['delete_message'].called

def test_delete_message_unauthorized(client, mock_message_service, sample_message):
    # Mock auth dependency for a user who is not the sender
    with patch('backend.dependencies.dep_auth.get_current_user', return_value={"id": "other_user", "type": "user"}):
        # Mock service response
        mock_message_service['get_message'].return_value = sample_message
        
        # Send request
        response = client.delete("/messages/message123")
        
        # Assertions
        assert response.status_code == 403
        assert "Only the sender" in response.json()["detail"]
        assert mock_message_service['get_message'].called
        assert not mock_message_service['delete_message'].called

def test_delete_message_not_found(client, mock_message_service):
    # Mock auth dependency
    with patch('backend.dependencies.dep_auth.get_current_user', return_value={"id": "user456", "type": "user"}):
        # Mock service response
        mock_message_service['get_message'].return_value = None
        
        # Send request
        response = client.delete("/messages/nonexistent")
        
        # Assertions
        assert response.status_code == 404
        assert "not found" in response.json()["detail"]
        assert mock_message_service['get_message'].called
        assert not mock_message_service['delete_message'].called