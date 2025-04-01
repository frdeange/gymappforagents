from azure.cosmos import ContainerProxy
from backend.models.mod_availability import Availability
from backend.schemas.sch_availability import AvailabilityCreate, AvailabilityUpdate
from backend.validators.val_availability import AvailabilityValidator
import uuid
from datetime import datetime, timezone, time
from typing import List, Optional

class AvailabilityService:
    @staticmethod
    def _serialize_time_slot(time_slot):
        """Convert time objects to string format"""
        return {
            "start_time": time_slot.start_time.strftime("%H:%M:%S"),
            "end_time": time_slot.end_time.strftime("%H:%M:%S")
        }

    @staticmethod
    def _deserialize_time_slot(time_slot_dict):
        """Convert time strings back to time objects"""
        return {
            "start_time": datetime.strptime(time_slot_dict["start_time"], "%H:%M:%S").time(),
            "end_time": datetime.strptime(time_slot_dict["end_time"], "%H:%M:%S").time()
        }

    @staticmethod
    def create_availability(db: ContainerProxy, availability: AvailabilityCreate) -> Availability:
        # Validate business rules
        AvailabilityValidator.validate_create_availability(availability)
        
        availability_id = str(uuid.uuid4())
        current_time = datetime.now(timezone.utc)
        
        # Serialize schedule with proper date/time handling
        serialized_schedule = []
        for day in availability.schedule:
            day_dict = {
                "available": day.available,
                "time_slots": [AvailabilityService._serialize_time_slot(slot) for slot in day.time_slots]
            }
            if day.day_of_week is not None:
                day_dict["day_of_week"] = day.day_of_week
            if day.date is not None:
                day_dict["date"] = day.date.replace(tzinfo=timezone.utc).isoformat()
            serialized_schedule.append(day_dict)

        availability_dict = {
            "id": availability_id,
            "trainer_id": availability.trainer_id,
            "center_id": availability.center_id,
            "recurrence_type": availability.recurrence_type,
            "schedule": serialized_schedule,
            "start_date": availability.start_date.replace(tzinfo=timezone.utc).isoformat(),
            "end_date": availability.end_date.replace(tzinfo=timezone.utc).isoformat() if availability.end_date else None,
            "created_at": current_time.isoformat(),
            "updated_at": current_time.isoformat()
        }
        
        db.create_item(body=availability_dict)
        
        # Convert back to model format for return
        return AvailabilityService._convert_to_model(availability_dict)

    @staticmethod
    def _convert_to_model(item: dict) -> Availability:
        """Convert a dictionary from storage format to model format"""
        # Convert schedule items
        schedule = []
        for day in item["schedule"]:
            day_dict = {
                "available": day["available"],
                "time_slots": []
            }
            # Handle time slots
            for slot in day["time_slots"]:
                time_slot = AvailabilityService._deserialize_time_slot(slot)
                day_dict["time_slots"].append(time_slot)
            
            # Handle date or day_of_week
            if "day_of_week" in day:
                day_dict["day_of_week"] = day["day_of_week"]
            if "date" in day and day["date"]:
                day_dict["date"] = datetime.fromisoformat(day["date"])
            
            schedule.append(day_dict)
        
        # Convert main datetime fields
        converted = {
            "id": item["id"],
            "trainer_id": item["trainer_id"],
            "center_id": item["center_id"],
            "recurrence_type": item["recurrence_type"],
            "schedule": schedule,
            "start_date": datetime.fromisoformat(item["start_date"]),
            "created_at": datetime.fromisoformat(item["created_at"]),
            "updated_at": datetime.fromisoformat(item["updated_at"])
        }
        
        if item.get("end_date"):
            converted["end_date"] = datetime.fromisoformat(item["end_date"])
        
        return Availability(**converted)

    @staticmethod
    def get_availability(db: ContainerProxy, availability_id: str) -> Optional[Availability]:
        query = f'SELECT * FROM c WHERE c.id = "{availability_id}"'
        items = list(db.query_items(query=query, enable_cross_partition_query=True))
        
        if items:
            return AvailabilityService._convert_to_model(items[0])
        return None

    @staticmethod
    def get_trainer_availabilities(db: ContainerProxy, trainer_id: str) -> List[Availability]:
        query = f'SELECT * FROM c WHERE c.trainer_id = "{trainer_id}"'
        items = list(db.query_items(query=query, enable_cross_partition_query=True))
        return [AvailabilityService._convert_to_model(item) for item in items]

    @staticmethod
    def update_availability(db: ContainerProxy, availability_id: str, availability: AvailabilityUpdate) -> Optional[Availability]:
        existing_availability = AvailabilityService.get_availability(db, availability_id)
        if existing_availability:
            # Validate business rules
            AvailabilityValidator.validate_update_availability(existing_availability.start_date, availability)
            
            # Update schedule if provided
            if availability.schedule is not None:
                serialized_schedule = []
                for day in availability.schedule:
                    day_dict = {
                        "available": day.available,
                        "time_slots": [AvailabilityService._serialize_time_slot(slot) for slot in day.time_slots]
                    }
                    if day.day_of_week is not None:
                        day_dict["day_of_week"] = day.day_of_week
                    if day.date is not None:
                        day_dict["date"] = day.date.replace(tzinfo=timezone.utc).isoformat()
                    serialized_schedule.append(day_dict)
                existing_availability.schedule = serialized_schedule

            # Update end date if provided
            if availability.end_date is not None:
                existing_availability.end_date = availability.end_date.replace(tzinfo=timezone.utc)
                
            existing_availability.updated_at = datetime.now(timezone.utc)
            
            # Convert to dictionary and serialize dates for storage
            availability_dict = {
                "id": existing_availability.id,
                "trainer_id": existing_availability.trainer_id,
                "center_id": existing_availability.center_id,
                "recurrence_type": existing_availability.recurrence_type,
                "schedule": existing_availability.schedule,
                "start_date": existing_availability.start_date.isoformat(),
                "end_date": existing_availability.end_date.isoformat() if existing_availability.end_date else None,
                "created_at": existing_availability.created_at.isoformat(),
                "updated_at": existing_availability.updated_at.isoformat()
            }
            
            db.upsert_item(body=availability_dict)
            return AvailabilityService._convert_to_model(availability_dict)
            
        return None

    @staticmethod
    def delete_availability(db: ContainerProxy, availability_id: str) -> bool:
        try:
            db.delete_item(item=availability_id, partition_key=availability_id)
            return True
        except Exception:
            return False

    @staticmethod
    def get_center_availabilities(db: ContainerProxy, center_id: str, start_date: datetime, end_date: datetime) -> List[Availability]:
        """Get all availabilities for a specific center within a date range"""
        start_date_str = start_date.replace(tzinfo=timezone.utc).isoformat()
        end_date_str = end_date.replace(tzinfo=timezone.utc).isoformat()
        
        query = f'''
        SELECT * FROM c 
        WHERE c.center_id = "{center_id}" 
        AND (c.end_date >= "{start_date_str}" OR c.end_date = null) 
        AND c.start_date <= "{end_date_str}"
        '''
        
        items = list(db.query_items(query=query, enable_cross_partition_query=True))
        return [AvailabilityService._convert_to_model(item) for item in items]