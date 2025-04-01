import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta, timezone
import uuid

from backend.services.svc_booking import BookingService
from backend.schemas.sch_booking import BookingCreate, BookingUpdate
from backend.models.mod_booking import Booking, BookingChange

class TestBookingService:
    @pytest.fixture
    def mock_db(self):
        return MagicMock()
    
    @pytest.fixture
    def booking_data(self):
        return BookingCreate(
            user_id="user123",
            trainer_id="trainer456",
            center_id="center789",
            start_time=datetime.now(timezone.utc) + timedelta(days=1),
            end_time=datetime.now(timezone.utc) + timedelta(days=1, hours=1),
            message="Test booking"
        )
    
    @pytest.fixture
    def existing_booking(self):
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
    def past_booking(self):
        start_time = datetime.now(timezone.utc) - timedelta(days=1)
        end_time = start_time + timedelta(hours=1)
        return Booking(
            id="booking456",
            user_id="user123",
            trainer_id="trainer456",
            center_id="center789",
            start_time=start_time,
            end_time=end_time,
            status="booked",
            message="Past booking",
            changes=[]
        )
    
    @patch('uuid.uuid4')
    @patch('backend.validators.val_booking.BookingValidator.validate_create_booking')
    def test_create_booking(self, mock_validate, mock_uuid, mock_db, booking_data):
        # Mock UUID
        mock_uuid.return_value = "test-uuid-1234"
        
        # Call the service
        result = BookingService.create_booking(mock_db, booking_data)
        
        # Assertions
        assert result.id == "test-uuid-1234"
        assert result.user_id == "user123"
        assert result.trainer_id == "trainer456"
        assert result.center_id == "center789"
        assert result.status == "booked"
        assert result.message == "Test booking"
        assert len(result.changes) == 0
        
        # Verify validator and DB were called
        mock_validate.assert_called_once_with(booking_data)
        mock_db.create_item.assert_called_once()
        
        # Verify correct data was passed to DB
        created_item = mock_db.create_item.call_args[1]['body']
        assert created_item["id"] == "test-uuid-1234"
        assert created_item["user_id"] == "user123"
        assert created_item["trainer_id"] == "trainer456"
        assert created_item["status"] == "booked"
    
    def test_get_booking_found(self, mock_db, existing_booking):
        # Convert to DB format
        db_item = {
            "id": existing_booking.id,
            "user_id": existing_booking.user_id,
            "trainer_id": existing_booking.trainer_id,
            "center_id": existing_booking.center_id,
            "start_time": existing_booking.start_time.isoformat(),
            "end_time": existing_booking.end_time.isoformat(),
            "status": existing_booking.status,
            "message": existing_booking.message,
            "changes": []
        }
        
        # Mock DB response
        mock_db.query_items.return_value = [db_item]
        
        # Call the service
        result = BookingService.get_booking(mock_db, "booking123")
        
        # Assertions
        assert result is not None
        assert result.id == "booking123"
        assert result.user_id == "user123"
        assert result.trainer_id == "trainer456"
        assert result.status == "booked"
        assert result.start_time == existing_booking.start_time
        assert result.end_time == existing_booking.end_time
    
    def test_get_booking_not_found(self, mock_db):
        # Mock empty DB response
        mock_db.query_items.return_value = []
        
        # Call the service
        result = BookingService.get_booking(mock_db, "nonexistent")
        
        # Assertions
        assert result is None
    
    def test_get_booking_with_changes(self, mock_db, existing_booking):
        # Add a change to the booking
        change_time = datetime.now(timezone.utc) - timedelta(hours=1)
        
        # Convert to DB format
        db_item = {
            "id": existing_booking.id,
            "user_id": existing_booking.user_id,
            "trainer_id": existing_booking.trainer_id,
            "center_id": existing_booking.center_id,
            "start_time": existing_booking.start_time.isoformat(),
            "end_time": existing_booking.end_time.isoformat(),
            "status": existing_booking.status,
            "message": existing_booking.message,
            "changes": [
                {
                    "timestamp": change_time.isoformat(),
                    "change_type": "modification",
                    "previous_start_time": (existing_booking.start_time - timedelta(hours=1)).isoformat(),
                    "previous_end_time": (existing_booking.end_time - timedelta(hours=1)).isoformat()
                }
            ]
        }
        
        # Mock DB response
        mock_db.query_items.return_value = [db_item]
        
        # Call the service
        result = BookingService.get_booking(mock_db, "booking123")
        
        # Assertions
        assert result is not None
        assert len(result.changes) == 1
        assert result.changes[0].timestamp == change_time
        assert result.changes[0].change_type == "modification"
        assert result.changes[0].previous_start_time is not None
    
    @patch('backend.services.svc_booking.datetime')
    def test_get_user_future_bookings(self, mock_datetime, mock_db, existing_booking):
        # Mock current time
        mock_now = datetime.now(timezone.utc)
        mock_datetime.now.return_value = mock_now
        mock_datetime.fromisoformat = datetime.fromisoformat
        
        # Convert to DB format
        db_item = {
            "id": existing_booking.id,
            "user_id": existing_booking.user_id,
            "trainer_id": existing_booking.trainer_id,
            "center_id": existing_booking.center_id,
            "start_time": existing_booking.start_time.isoformat(),
            "end_time": existing_booking.end_time.isoformat(),
            "status": existing_booking.status,
            "message": existing_booking.message,
            "changes": []
        }
        
        # Mock DB response
        mock_db.query_items.return_value = [db_item]
        
        # Call the service
        result = BookingService.get_user_future_bookings(mock_db, "user123")
        
        # Assertions
        assert len(result) == 1
        assert result[0].id == "booking123"
        assert result[0].user_id == "user123"
        
        # Verify query
        mock_db.query_items.assert_called_once()
        query = mock_db.query_items.call_args[1]['query']
        assert "user123" in query
        assert mock_now.isoformat() in query
        assert "c.start_time > " in query
    
    @patch('backend.services.svc_booking.datetime')
    def test_get_user_past_bookings(self, mock_datetime, mock_db, past_booking):
        # Mock current time
        mock_now = datetime.now(timezone.utc)
        mock_datetime.now.return_value = mock_now
        mock_datetime.fromisoformat = datetime.fromisoformat
        
        # Convert to DB format
        db_item = {
            "id": past_booking.id,
            "user_id": past_booking.user_id,
            "trainer_id": past_booking.trainer_id,
            "center_id": past_booking.center_id,
            "start_time": past_booking.start_time.isoformat(),
            "end_time": past_booking.end_time.isoformat(),
            "status": past_booking.status,
            "message": past_booking.message,
            "changes": []
        }
        
        # Mock DB response
        mock_db.query_items.return_value = [db_item]
        
        # Call the service
        result = BookingService.get_user_past_bookings(mock_db, "user123")
        
        # Assertions
        assert len(result) == 1
        assert result[0].id == "booking456"
        assert result[0].message == "Past booking"
        
        # Verify query
        mock_db.query_items.assert_called_once()
        query = mock_db.query_items.call_args[1]['query']
        assert "user123" in query
        assert mock_now.isoformat() in query
        assert "c.start_time < " in query
    
    @patch('backend.validators.val_booking.BookingValidator.validate_update_booking')
    @patch('backend.services.svc_booking.datetime')
    def test_update_booking_with_changes(self, mock_datetime, mock_validate, mock_db, existing_booking):
        # Mock the get_booking method
        with patch.object(BookingService, 'get_booking', return_value=existing_booking):
            # Mock current time
            mock_now = datetime.now(timezone.utc)
            mock_datetime.now.return_value = mock_now
            mock_datetime.fromisoformat = datetime.fromisoformat
            
            # New booking time
            new_start_time = existing_booking.start_time + timedelta(hours=2)
            new_end_time = existing_booking.end_time + timedelta(hours=2)
            
            # Create update data
            update_data = BookingUpdate(
                start_time=new_start_time,
                end_time=new_end_time,
                message="Updated message"
            )
            
            # Call the service
            result = BookingService.update_booking(mock_db, "booking123", update_data)
            
            # Assertions
            assert result is not None
            assert result.id == "booking123"
            assert result.start_time == new_start_time
            assert result.end_time == new_end_time
            assert result.message == "Updated message"
            assert len(result.changes) == 1
            assert result.changes[0].timestamp == mock_now
            assert result.changes[0].change_type == "modification"
            assert result.changes[0].previous_start_time == existing_booking.start_time
            
            # Verify validator and DB were called
            mock_validate.assert_called_once()
            mock_db.upsert_item.assert_called_once()
    
    def test_update_booking_not_found(self, mock_db):
        # Mock the get_booking method to return None
        with patch.object(BookingService, 'get_booking', return_value=None):
            # Create update data
            update_data = BookingUpdate(
                message="Updated message"
            )
            
            # Call the service
            result = BookingService.update_booking(mock_db, "nonexistent", update_data)
            
            # Assertions
            assert result is None
            
            # Verify DB was not called
            mock_db.upsert_item.assert_not_called()
    
    @patch('backend.validators.val_booking.BookingValidator.validate_cancel_booking')
    @patch('backend.services.svc_booking.datetime')
    def test_cancel_booking(self, mock_datetime, mock_validate, mock_db, existing_booking):
        # Mock the get_booking method
        with patch.object(BookingService, 'get_booking', return_value=existing_booking):
            # Mock current time
            mock_now = datetime.now(timezone.utc)
            mock_datetime.now.return_value = mock_now
            mock_datetime.fromisoformat = datetime.fromisoformat
            
            # Call the service
            result = BookingService.cancel_booking(mock_db, "booking123")
            
            # Assertions
            assert result is not None
            assert result.id == "booking123"
            assert result.status == "cancelled"
            assert len(result.changes) == 1
            assert result.changes[0].timestamp == mock_now
            assert result.changes[0].change_type == "cancellation"
            
            # Verify validator and DB were called
            mock_validate.assert_called_once_with(existing_booking.start_time)
            mock_db.upsert_item.assert_called_once()
    
    def test_cancel_booking_not_found(self, mock_db):
        # Mock the get_booking method to return None
        with patch.object(BookingService, 'get_booking', return_value=None):
            # Call the service
            result = BookingService.cancel_booking(mock_db, "nonexistent")
            
            # Assertions
            assert result is None
            
            # Verify DB was not called
            mock_db.upsert_item.assert_not_called()