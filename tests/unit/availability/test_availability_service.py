import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, time, timezone
import uuid

from backend.services.svc_availability import AvailabilityService
from backend.schemas.sch_availability import AvailabilityCreate, AvailabilityUpdate, DaySchedule, TimeSlot
from backend.models.mod_availability import Availability, RecurrenceType

class TestAvailabilityService:
    @pytest.fixture
    def mock_db(self):
        return MagicMock()
    
    @pytest.fixture
    def sample_time_slot(self):
        return TimeSlot(
            start_time=time(9, 0),
            end_time=time(10, 0)
        )
    
    @pytest.fixture
    def sample_day_schedule(self, sample_time_slot):
        return DaySchedule(
            day_of_week=1,  # Monday
            available=True,
            time_slots=[sample_time_slot]
        )
    
    @pytest.fixture
    def sample_date_schedule(self, sample_time_slot):
        return DaySchedule(
            date=datetime(2025, 4, 1),
            available=True,
            time_slots=[sample_time_slot]
        )
    
    @pytest.fixture
    def weekly_availability_data(self, sample_day_schedule):
        return AvailabilityCreate(
            trainer_id="trainer123",
            center_id="center456",
            recurrence_type=RecurrenceType.WEEKLY,
            schedule=[sample_day_schedule],
            start_date=datetime(2025, 4, 1),
            end_date=datetime(2025, 6, 30)
        )
    
    @pytest.fixture
    def one_time_availability_data(self, sample_date_schedule):
        return AvailabilityCreate(
            trainer_id="trainer123",
            center_id="center456",
            recurrence_type=RecurrenceType.ONE_TIME,
            schedule=[sample_date_schedule],
            start_date=datetime(2025, 4, 1),
            end_date=None
        )
    
    def test_serialize_time_slot(self, sample_time_slot):
        serialized = AvailabilityService._serialize_time_slot(sample_time_slot)
        assert serialized["start_time"] == "09:00:00"
        assert serialized["end_time"] == "10:00:00"
    
    def test_deserialize_time_slot(self):
        time_slot_dict = {
            "start_time": "09:00:00",
            "end_time": "10:00:00"
        }
        deserialized = AvailabilityService._deserialize_time_slot(time_slot_dict)
        assert deserialized["start_time"] == time(9, 0)
        assert deserialized["end_time"] == time(10, 0)
    
    @patch('uuid.uuid4')
    @patch('backend.services.svc_availability.datetime')
    def test_create_weekly_availability(self, mock_datetime, mock_uuid, mock_db, weekly_availability_data):
        # Mock the datetime.now call
        mock_now = datetime(2025, 3, 31, 12, 0, 0, tzinfo=timezone.utc)
        mock_datetime.now.return_value = mock_now
        mock_datetime.fromisoformat = datetime.fromisoformat
        mock_datetime.strptime = datetime.strptime
        
        # Mock UUID generation
        mock_uuid_value = "test-uuid-1234"
        mock_uuid.return_value = mock_uuid_value
        
        # Call the service method
        result = AvailabilityService.create_availability(mock_db, weekly_availability_data)
        
        # Check that the DB was called correctly
        mock_db.create_item.assert_called_once()
        
        # Verify the created item
        created_item = mock_db.create_item.call_args[1]['body']
        assert created_item["id"] == mock_uuid_value
        assert created_item["trainer_id"] == "trainer123"
        assert created_item["center_id"] == "center456"
        assert created_item["recurrence_type"] == "weekly"
        assert len(created_item["schedule"]) == 1
        assert created_item["schedule"][0]["day_of_week"] == 1
        assert created_item["schedule"][0]["available"] is True
        
        # Verify time slots in the schedule
        time_slots = created_item["schedule"][0]["time_slots"]
        assert len(time_slots) == 1
        assert time_slots[0]["start_time"] == "09:00:00"
        assert time_slots[0]["end_time"] == "10:00:00"
        
        # Verify the returned model
        assert isinstance(result, Availability)
        assert result.id == mock_uuid_value
        assert result.trainer_id == "trainer123"
        assert result.center_id == "center456"
        assert result.recurrence_type == RecurrenceType.WEEKLY
    
    @patch('uuid.uuid4')
    @patch('backend.services.svc_availability.datetime')
    def test_create_one_time_availability(self, mock_datetime, mock_uuid, mock_db, one_time_availability_data):
        # Mock the datetime.now call
        mock_now = datetime(2025, 3, 31, 12, 0, 0, tzinfo=timezone.utc)
        mock_datetime.now.return_value = mock_now
        mock_datetime.fromisoformat = datetime.fromisoformat
        mock_datetime.strptime = datetime.strptime
        
        # Mock UUID generation
        mock_uuid_value = "test-uuid-1234"
        mock_uuid.return_value = mock_uuid_value
        
        # Call the service method
        result = AvailabilityService.create_availability(mock_db, one_time_availability_data)
        
        # Check that the DB was called correctly
        mock_db.create_item.assert_called_once()
        
        # Verify the created item
        created_item = mock_db.create_item.call_args[1]['body']
        assert created_item["id"] == mock_uuid_value
        assert created_item["recurrence_type"] == "one_time"
        assert len(created_item["schedule"]) == 1
        assert "date" in created_item["schedule"][0]
        assert "day_of_week" not in created_item["schedule"][0]
        assert created_item["schedule"][0]["available"] is True
        
        # Verify the returned model
        assert isinstance(result, Availability)
        assert result.recurrence_type == RecurrenceType.ONE_TIME
        assert result.end_date is None
    
    def test_get_availability_found(self, mock_db):
        # Mock DB response
        mock_db.query_items.return_value = [
            {
                "id": "test-id",
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
                "start_date": "2025-04-01T00:00:00+00:00",
                "end_date": "2025-06-30T00:00:00+00:00",
                "created_at": "2025-03-31T12:00:00+00:00",
                "updated_at": "2025-03-31T12:00:00+00:00"
            }
        ]
        
        # Call the service method
        result = AvailabilityService.get_availability(mock_db, "test-id")
        
        # Verify the result
        assert result is not None
        assert result.id == "test-id"
        assert result.trainer_id == "trainer123"
        assert result.recurrence_type == RecurrenceType.WEEKLY
        assert len(result.schedule) == 1
        assert result.schedule[0]["day_of_week"] == 1
        assert result.schedule[0]["available"] is True
        assert len(result.schedule[0]["time_slots"]) == 1
        
        # Verify time slot converted correctly
        time_slot = result.schedule[0]["time_slots"][0]
        assert time_slot["start_time"] == time(9, 0)
        assert time_slot["end_time"] == time(10, 0)
    
    def test_get_availability_not_found(self, mock_db):
        # Mock DB response for empty result
        mock_db.query_items.return_value = []
        
        # Call the service method
        result = AvailabilityService.get_availability(mock_db, "nonexistent-id")
        
        # Verify the result
        assert result is None
    
    def test_get_trainer_availabilities(self, mock_db):
        # Mock DB response
        mock_db.query_items.return_value = [
            {
                "id": "avail1",
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
                "start_date": "2025-04-01T00:00:00+00:00",
                "end_date": "2025-06-30T00:00:00+00:00",
                "created_at": "2025-03-31T12:00:00+00:00",
                "updated_at": "2025-03-31T12:00:00+00:00"
            },
            {
                "id": "avail2",
                "trainer_id": "trainer123",
                "center_id": "center789",
                "recurrence_type": "one_time",
                "schedule": [
                    {
                        "date": "2025-05-01T00:00:00+00:00",
                        "available": True,
                        "time_slots": [
                            {
                                "start_time": "14:00:00",
                                "end_time": "15:00:00"
                            }
                        ]
                    }
                ],
                "start_date": "2025-05-01T00:00:00+00:00",
                "end_date": null,
                "created_at": "2025-03-31T12:00:00+00:00",
                "updated_at": "2025-03-31T12:00:00+00:00"
            }
        ]
        
        # Call the service method
        result = AvailabilityService.get_trainer_availabilities(mock_db, "trainer123")
        
        # Verify the result
        assert len(result) == 2
        assert result[0].id == "avail1"
        assert result[0].recurrence_type == RecurrenceType.WEEKLY
        assert result[1].id == "avail2"
        assert result[1].recurrence_type == RecurrenceType.ONE_TIME
    
    def test_update_availability(self, mock_db):
        # Mock the get_availability method
        original_availability = Availability(
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
        
        with patch.object(AvailabilityService, 'get_availability', return_value=original_availability) as mock_get:
            # Create update data with new end date
            update_data = AvailabilityUpdate(
                end_date=datetime(2025, 5, 31, tzinfo=timezone.utc)
            )
            
            # Call the service method
            with patch('backend.services.svc_availability.datetime') as mock_datetime:
                # Mock the datetime.now call
                mock_now = datetime(2025, 4, 10, 12, 0, 0, tzinfo=timezone.utc)
                mock_datetime.now.return_value = mock_now
                mock_datetime.fromisoformat = datetime.fromisoformat
                
                result = AvailabilityService.update_availability(mock_db, "test-id", update_data)
            
            # Verify the result
            assert result is not None
            assert result.id == "test-id"
            assert result.end_date == datetime(2025, 5, 31, tzinfo=timezone.utc)
            assert result.updated_at == datetime(2025, 4, 10, 12, 0, 0, tzinfo=timezone.utc)
            
            # Verify DB was called
            mock_db.upsert_item.assert_called_once()
    
    def test_update_availability_not_found(self, mock_db):
        # Mock the get_availability method to return None
        with patch.object(AvailabilityService, 'get_availability', return_value=None):
            # Create update data
            update_data = AvailabilityUpdate(
                end_date=datetime(2025, 5, 31)
            )
            
            # Call the service method
            result = AvailabilityService.update_availability(mock_db, "nonexistent-id", update_data)
            
            # Verify the result
            assert result is None
            
            # Verify DB was not called
            mock_db.upsert_item.assert_not_called()
    
    def test_delete_availability_success(self, mock_db):
        # Configure mock to not raise exceptions
        mock_db.delete_item.return_value = {}
        
        # Call the service method
        result = AvailabilityService.delete_availability(mock_db, "test-id")
        
        # Verify the result
        assert result is True
        mock_db.delete_item.assert_called_once_with(item="test-id", partition_key="test-id")
    
    def test_delete_availability_failure(self, mock_db):
        # Configure mock to raise an exception
        mock_db.delete_item.side_effect = Exception("Item not found")
        
        # Call the service method
        result = AvailabilityService.delete_availability(mock_db, "nonexistent-id")
        
        # Verify the result
        assert result is False
        mock_db.delete_item.assert_called_once_with(item="nonexistent-id", partition_key="nonexistent-id")
    
    def test_get_center_availabilities(self, mock_db):
        # Mock DB response
        mock_db.query_items.return_value = [
            {
                "id": "avail1",
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
                "start_date": "2025-04-01T00:00:00+00:00",
                "end_date": "2025-06-30T00:00:00+00:00",
                "created_at": "2025-03-31T12:00:00+00:00",
                "updated_at": "2025-03-31T12:00:00+00:00"
            }
        ]
        
        # Define date range
        start_date = datetime(2025, 4, 1, tzinfo=timezone.utc)
        end_date = datetime(2025, 4, 30, tzinfo=timezone.utc)
        
        # Call the service method
        result = AvailabilityService.get_center_availabilities(mock_db, "center456", start_date, end_date)
        
        # Verify the result
        assert len(result) == 1
        assert result[0].id == "avail1"
        assert result[0].center_id == "center456"
        
        # Verify query parameters
        mock_db.query_items.assert_called_once()
        query = mock_db.query_items.call_args[1]['query']
        assert "center456" in query
        assert "2025-04-01T00:00:00+00:00" in query
        assert "2025-04-30T00:00:00+00:00" in query