import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone, timedelta
import uuid

from backend.services.svc_message import MessageService
from backend.models.mod_message import Message, MessageType, MessageStatus, UserType
from backend.schemas.sch_message import IndividualMessageCreate, MassMessageCreate, MessageUpdate, ConversationResponse
from backend.validators.val_message import MessageValidationError

class TestMessageService:
    @pytest.fixture
    def mock_db(self):
        return MagicMock()
    
    @pytest.fixture
    def individual_message_data(self):
        return IndividualMessageCreate(
            recipient_id="recipient123",
            recipient_type=UserType.USER,
            content="Test message",
            parent_message_id=None
        )
    
    @pytest.fixture
    def mass_message_data(self):
        return MassMessageCreate(
            recipient_ids=["user1", "user2", "user3"],
            recipient_type=UserType.USER,
            content="Mass test message"
        )
    
    @pytest.fixture
    def existing_message(self):
        current_time = datetime.now(timezone.utc)
        return Message(
            id="message123",
            sender_id="sender456",
            sender_type=UserType.TRAINER,
            recipient_id="recipient789",
            recipient_type=UserType.USER,
            message_type=MessageType.INDIVIDUAL,
            content="Hello!",
            status=MessageStatus.SENT,
            created_at=current_time,
            read_at=None,
            parent_message_id=None,
            mass_recipient_ids=None
        )
    
    @patch('uuid.uuid4')
    @patch('backend.services.svc_message.datetime')
    @patch('backend.validators.val_message.MessageValidator.validate_create_individual_message')
    def test_create_individual_message(self, mock_validate, mock_datetime, mock_uuid, mock_db, individual_message_data):
        # Mock UUID and datetime
        mock_uuid.return_value = "test-uuid-1234"
        current_time = datetime.now(timezone.utc)
        mock_datetime.now.return_value = current_time
        mock_datetime.fromisoformat = datetime.fromisoformat
        
        # Call the service
        result = MessageService.create_individual_message(
            mock_db, 
            individual_message_data, 
            sender_id="sender123",
            sender_type=UserType.TRAINER
        )
        
        # Assertions
        assert result.id == "test-uuid-1234"
        assert result.sender_id == "sender123"
        assert result.sender_type == UserType.TRAINER
        assert result.recipient_id == "recipient123"
        assert result.recipient_type == UserType.USER
        assert result.message_type == MessageType.INDIVIDUAL
        assert result.content == "Test message"
        assert result.status == MessageStatus.SENT
        assert result.created_at == current_time
        assert result.read_at is None
        
        # Verify validator and DB were called
        mock_validate.assert_called_once_with(UserType.TRAINER, individual_message_data)
        mock_db.create_item.assert_called_once()
        
        # Verify correct data was passed to DB
        created_item = mock_db.create_item.call_args[1]['body']
        assert created_item["id"] == "test-uuid-1234"
        assert created_item["sender_id"] == "sender123"
        assert created_item["content"] == "Test message"
    
    @patch('uuid.uuid4')
    @patch('backend.services.svc_message.datetime')
    def test_create_mass_message(self, mock_datetime, mock_uuid, mock_db, mass_message_data):
        # Mock datetime
        current_time = datetime.now(timezone.utc)
        mock_datetime.now.return_value = current_time
        mock_datetime.fromisoformat = datetime.fromisoformat
        
        # Mock UUID to return different values for each call
        mock_uuid.side_effect = ["uuid1", "uuid2", "uuid3"]
        
        # Call the service
        result = MessageService.create_mass_message(
            mock_db, 
            mass_message_data, 
            sender_id="admin123"
        )
        
        # Assertions
        assert result.id == "uuid1"  # First UUID
        assert result.sender_id == "admin123"
        assert result.sender_type == UserType.ADMIN
        assert result.message_type == MessageType.MASS
        assert result.content == "Mass test message"
        assert result.mass_recipient_ids == ["user1", "user2", "user3"]
        
        # Verify DB was called once for each recipient
        assert mock_db.create_item.call_count == 3
        
        # Check first recipient's message
        first_item = mock_db.create_item.call_args_list[0][1]['body']
        assert first_item["id"] == "uuid1"
        assert first_item["recipient_id"] == "user1"
        
        # Check last recipient's message
        last_item = mock_db.create_item.call_args_list[2][1]['body']
        assert last_item["id"] == "uuid3"
        assert last_item["recipient_id"] == "user3"
    
    @patch('uuid.uuid4')
    @patch('backend.services.svc_message.datetime')
    def test_create_mass_message_empty_recipients(self, mock_datetime, mock_uuid, mock_db):
        # Create message with empty recipient list
        empty_message = MassMessageCreate(
            recipient_ids=[],
            recipient_type=UserType.USER,
            content="Empty message"
        )
        
        # Test for exception
        with pytest.raises(MessageValidationError) as exc_info:
            MessageService.create_mass_message(mock_db, empty_message, "admin123")
        
        # Verify error message
        assert "No messages were created" in str(exc_info.value)
        
        # Verify DB was not called
        mock_db.create_item.assert_not_called()
    
    def test_get_message_found(self, mock_db, existing_message):
        # Convert to DB format
        db_item = {
            "id": existing_message.id,
            "sender_id": existing_message.sender_id,
            "sender_type": existing_message.sender_type,
            "recipient_id": existing_message.recipient_id,
            "recipient_type": existing_message.recipient_type,
            "message_type": existing_message.message_type,
            "content": existing_message.content,
            "status": existing_message.status,
            "created_at": existing_message.created_at.isoformat(),
            "read_at": None,
            "parent_message_id": existing_message.parent_message_id,
            "mass_recipient_ids": existing_message.mass_recipient_ids
        }
        
        # Mock DB response
        mock_db.query_items.return_value = [db_item]
        
        # Call the service
        result = MessageService.get_message(mock_db, "message123")
        
        # Assertions
        assert result is not None
        assert result.id == "message123"
        assert result.sender_id == "sender456"
        assert result.recipient_id == "recipient789"
        assert result.message_type == MessageType.INDIVIDUAL
        assert result.content == "Hello!"
        assert result.created_at == existing_message.created_at
    
    def test_get_message_not_found(self, mock_db):
        # Mock empty DB response
        mock_db.query_items.return_value = []
        
        # Call the service
        result = MessageService.get_message(mock_db, "nonexistent")
        
        # Assertions
        assert result is None
    
    def test_get_conversation(self, mock_db, existing_message):
        # Mock datetime for conversion
        with patch('backend.services.svc_message.datetime') as mock_datetime:
            mock_datetime.fromisoformat = datetime.fromisoformat
            
            # Create additional messages for the conversation
            message1 = existing_message.copy()
            message1.id = "message1"
            message1.sender_id = "user1"
            message1.recipient_id = "user2"
            
            message2 = existing_message.copy()
            message2.id = "message2"
            message2.sender_id = "user2"
            message2.recipient_id = "user1"
            
            # Convert to DB format
            db_items = [
                {
                    "id": message1.id,
                    "sender_id": message1.sender_id,
                    "sender_type": message1.sender_type,
                    "recipient_id": message1.recipient_id,
                    "recipient_type": message1.recipient_type,
                    "message_type": message1.message_type,
                    "content": message1.content,
                    "status": message1.status,
                    "created_at": message1.created_at.isoformat(),
                    "read_at": None,
                    "parent_message_id": message1.parent_message_id,
                    "mass_recipient_ids": message1.mass_recipient_ids
                },
                {
                    "id": message2.id,
                    "sender_id": message2.sender_id,
                    "sender_type": message2.sender_type,
                    "recipient_id": message2.recipient_id,
                    "recipient_type": message2.recipient_type,
                    "message_type": message2.message_type,
                    "content": message2.content,
                    "status": message2.status,
                    "created_at": message2.created_at.isoformat(),
                    "read_at": None,
                    "parent_message_id": message2.parent_message_id,
                    "mass_recipient_ids": message2.mass_recipient_ids
                }
            ]
            
            # Mock DB response for different queries
            mock_db.query_items.side_effect = [
                db_items,  # For messages query
                [2],       # For unread count query
                [5]        # For total count query
            ]
            
            # Call the service
            result = MessageService.get_conversation(mock_db, "user1", "user2", limit=10, offset=0)
            
            # Assertions
            assert isinstance(result, ConversationResponse)
            assert len(result.messages) == 2
            assert result.messages[0].id in ["message1", "message2"]
            assert result.messages[1].id in ["message1", "message2"]
            assert result.total_messages == 5
            assert result.unread_count == 2
            
            # Verify query calls
            assert mock_db.query_items.call_count == 3
    
    def test_get_user_conversations(self, mock_db, existing_message):
        # Mock datetime for conversion
        with patch('backend.services.svc_message.datetime') as mock_datetime:
            mock_datetime.fromisoformat = datetime.fromisoformat
            
            # Create message in DB format
            db_item = {
                "id": existing_message.id,
                "sender_id": existing_message.sender_id,
                "sender_type": existing_message.sender_type,
                "recipient_id": existing_message.recipient_id,
                "recipient_type": existing_message.recipient_type,
                "message_type": existing_message.message_type,
                "content": existing_message.content,
                "status": existing_message.status,
                "created_at": existing_message.created_at.isoformat(),
                "read_at": None,
                "parent_message_id": existing_message.parent_message_id,
                "mass_recipient_ids": existing_message.mass_recipient_ids
            }
            
            # Mock DB response
            mock_db.query_items.return_value = [db_item]
            
            # Call the service
            result = MessageService.get_user_conversations(mock_db, "sender456")
            
            # Assertions
            assert len(result) == 1
            assert result[0].id == "message123"
            assert result[0].sender_id == "sender456"
            assert result[0].recipient_id == "recipient789"
            
            # Verify query was called with correct parameters
            mock_db.query_items.assert_called_once()
            query = mock_db.query_items.call_args[1]['query']
            assert "sender456" in query
            assert MessageType.INDIVIDUAL in query
    
    @patch('backend.validators.val_message.MessageValidator.validate_update_message')
    def test_update_message(self, mock_validate, mock_db, existing_message):
        # Mock the get_message method
        with patch.object(MessageService, 'get_message', return_value=existing_message):
            # Create update data
            update = MessageUpdate(
                status=MessageStatus.READ,
                read_at=datetime.now(timezone.utc)
            )
            
            # Call the service
            result = MessageService.update_message(mock_db, "message123", update)
            
            # Assertions
            assert result is not None
            assert result.id == "message123"
            assert result.status == MessageStatus.READ
            assert result.read_at is not None
            
            # Verify validator and DB were called
            mock_validate.assert_called_once_with(update)
            mock_db.upsert_item.assert_called_once()
            
            # Verify correct data was passed to DB
            updated_item = mock_db.upsert_item.call_args[1]['body']
            assert updated_item["id"] == "message123"
            assert updated_item["status"] == "read"
            assert updated_item["read_at"] is not None
    
    def test_update_message_not_found(self, mock_db):
        # Mock the get_message method to return None
        with patch.object(MessageService, 'get_message', return_value=None):
            # Create update data
            update = MessageUpdate(
                status=MessageStatus.READ,
                read_at=datetime.now(timezone.utc)
            )
            
            # Call the service
            result = MessageService.update_message(mock_db, "nonexistent", update)
            
            # Assertions
            assert result is None
            
            # Verify DB was not called
            mock_db.upsert_item.assert_not_called()
    
    @patch('backend.services.svc_message.datetime')
    def test_mark_conversation_as_read(self, mock_datetime, mock_db, existing_message):
        # Mock current time
        current_time = datetime.now(timezone.utc)
        mock_datetime.now.return_value = current_time
        mock_datetime.fromisoformat = datetime.fromisoformat
        
        # Create message in DB format
        db_item = {
            "id": existing_message.id,
            "sender_id": existing_message.sender_id,
            "sender_type": existing_message.sender_type,
            "recipient_id": existing_message.recipient_id,
            "recipient_type": existing_message.recipient_type,
            "message_type": existing_message.message_type,
            "content": existing_message.content,
            "status": existing_message.status,
            "created_at": existing_message.created_at.isoformat(),
            "read_at": None,
            "parent_message_id": existing_message.parent_message_id,
            "mass_recipient_ids": existing_message.mass_recipient_ids
        }
        
        # Mock DB response
        mock_db.query_items.return_value = [db_item]
        
        # Call the service
        result = MessageService.mark_conversation_as_read(mock_db, "recipient789", "sender456")
        
        # Assertions
        assert len(result) == 1
        assert result[0].id == "message123"
        assert result[0].status == MessageStatus.READ
        assert result[0].read_at == current_time
        
        # Verify DB was updated
        mock_db.upsert_item.assert_called_once()
        updated_item = mock_db.upsert_item.call_args[1]['body']
        assert updated_item["status"] == "read"
        assert updated_item["read_at"] == current_time.isoformat()
    
    def test_delete_message_success(self, mock_db):
        # Configure mock to not raise exceptions
        mock_db.delete_item.return_value = {}
        
        # Call the service
        result = MessageService.delete_message(mock_db, "message123")
        
        # Assertions
        assert result is True
        mock_db.delete_item.assert_called_once_with(item="message123", partition_key="message123")
    
    def test_delete_message_failure(self, mock_db):
        # Configure mock to raise an exception
        mock_db.delete_item.side_effect = Exception("Item not found")
        
        # Call the service
        result = MessageService.delete_message(mock_db, "nonexistent")
        
        # Assertions
        assert result is False
        mock_db.delete_item.assert_called_once_with(item="nonexistent", partition_key="nonexistent")