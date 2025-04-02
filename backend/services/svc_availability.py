from azure.cosmos import ContainerProxy
from backend.models.mod_availability import Availability
from backend.schemas.sch_availability import AvailabilityCreate, AvailabilityUpdate
from backend.validators.val_availability import AvailabilityValidator
import uuid
from datetime import datetime, timezone, time
from typing import List, Optional
from backend.configuration.monitor import log_event, log_exception, start_span

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
        try:
            with start_span("create_availability", attributes={"trainer_id": availability.trainer_id, "center_id": availability.center_id}):
                log_event("Create availability started", {
                    "trainer_id": availability.trainer_id,
                    "center_id": availability.center_id,
                    "recurrence_type": availability.recurrence_type
                })
                
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
                
                log_event("Availability created successfully", {
                    "availability_id": availability_id,
                    "trainer_id": availability.trainer_id,
                    "center_id": availability.center_id
                })
                
                # Convert back to model format for return
                return AvailabilityService._convert_to_model(availability_dict)
        except Exception as e:
            log_exception(e, {
                "operation": "create_availability",
                "trainer_id": availability.trainer_id,
                "center_id": availability.center_id
            })
            raise

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
        try:
            with start_span("get_availability", attributes={"availability_id": availability_id}):
                log_event("Retrieving availability", {"availability_id": availability_id})
                
                query = f'SELECT * FROM c WHERE c.id = "{availability_id}"'
                items = list(db.query_items(query=query, enable_cross_partition_query=True))
                
                if items:
                    log_event("Availability retrieved successfully", {"availability_id": availability_id})
                    return AvailabilityService._convert_to_model(items[0])
                
                log_event("Availability not found", {"availability_id": availability_id})
                return None
        except Exception as e:
            log_exception(e, {"operation": "get_availability", "availability_id": availability_id})
            raise

    @staticmethod
    def get_trainer_availabilities(db: ContainerProxy, trainer_id: str) -> List[Availability]:
        try:
            with start_span("get_trainer_availabilities", attributes={"trainer_id": trainer_id}):
                log_event("Retrieving trainer availabilities", {"trainer_id": trainer_id})
                
                query = f'SELECT * FROM c WHERE c.trainer_id = "{trainer_id}"'
                items = list(db.query_items(query=query, enable_cross_partition_query=True))
                
                result = [AvailabilityService._convert_to_model(item) for item in items]
                log_event("Trainer availabilities retrieved", {
                    "trainer_id": trainer_id,
                    "count": len(result)
                })
                
                return result
        except Exception as e:
            log_exception(e, {"operation": "get_trainer_availabilities", "trainer_id": trainer_id})
            raise

    @staticmethod
    def update_availability(db: ContainerProxy, availability_id: str, availability: AvailabilityUpdate) -> Optional[Availability]:
        try:
            with start_span("update_availability", attributes={"availability_id": availability_id}):
                log_event("Update availability started", {"availability_id": availability_id})
                
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
                    
                    log_event("Availability updated successfully", {
                        "availability_id": availability_id,
                        "trainer_id": existing_availability.trainer_id,
                        "center_id": existing_availability.center_id
                    })
                    
                    return AvailabilityService._convert_to_model(availability_dict)
                
                log_event("Availability not found for update", {"availability_id": availability_id})
                return None
        except Exception as e:
            log_exception(e, {"operation": "update_availability", "availability_id": availability_id})
            raise

    @staticmethod
    def delete_availability(db: ContainerProxy, availability_id: str) -> bool:
        try:
            with start_span("delete_availability", attributes={"availability_id": availability_id}):
                log_event("Delete availability started", {"availability_id": availability_id})
                
                db.delete_item(item=availability_id, partition_key=availability_id)
                
                log_event("Availability deleted successfully", {"availability_id": availability_id})
                return True
        except Exception as e:
            log_exception(e, {"operation": "delete_availability", "availability_id": availability_id})
            return False

    @staticmethod
    def get_center_availabilities(db: ContainerProxy, center_id: str, start_date: datetime, end_date: datetime) -> List[Availability]:
        """Get all availabilities for a specific center within a date range"""
        try:
            with start_span("get_center_availabilities", attributes={
                "center_id": center_id,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat()
            }):
                log_event("Retrieving center availabilities", {
                    "center_id": center_id,
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat()
                })
                
                start_date_str = start_date.replace(tzinfo=timezone.utc).isoformat()
                end_date_str = end_date.replace(tzinfo=timezone.utc).isoformat()
                
                query = f'''
                SELECT * FROM c 
                WHERE c.center_id = "{center_id}" 
                AND (c.end_date >= "{start_date_str}" OR c.end_date = null) 
                AND c.start_date <= "{end_date_str}"
                '''
                
                items = list(db.query_items(query=query, enable_cross_partition_query=True))
                result = [AvailabilityService._convert_to_model(item) for item in items]
                
                log_event("Center availabilities retrieved", {
                    "center_id": center_id,
                    "count": len(result)
                })
                
                return result
        except Exception as e:
            log_exception(e, {
                "operation": "get_center_availabilities",
                "center_id": center_id,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat()
            })
            raise