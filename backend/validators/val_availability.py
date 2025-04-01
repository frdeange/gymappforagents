from datetime import datetime, timezone
from fastapi import HTTPException
from backend.schemas.sch_availability import AvailabilityCreate, AvailabilityUpdate
from backend.models.mod_availability import RecurrenceType

class AvailabilityValidationError(HTTPException):
    def __init__(self, detail: str):
        super().__init__(status_code=400, detail=detail)

class AvailabilityValidator:
    @staticmethod
    def _get_current_time():
        """Get current time as UTC timezone-aware datetime"""
        return datetime.now(timezone.utc)

    @staticmethod
    def validate_time_slots(schedule):
        """Validate that time slots don't overlap within each day"""
        for day in schedule:
            sorted_slots = sorted(day.time_slots, key=lambda x: x.start_time)
            for i in range(len(sorted_slots) - 1):
                if sorted_slots[i].end_time > sorted_slots[i + 1].start_time:
                    raise AvailabilityValidationError(
                        "Time slots cannot overlap"
                    )

    @staticmethod
    def validate_dates(start_date: datetime, end_date: datetime = None):
        """Validate start and end dates"""
        current_time = AvailabilityValidator._get_current_time()
        
        if start_date < current_time:
            raise AvailabilityValidationError(
                "Start date cannot be in the past"
            )
            
        if end_date and end_date <= start_date:
            raise AvailabilityValidationError(
                "End date must be after start date"
            )

    @staticmethod
    def validate_recurrence_schedule(recurrence_type: RecurrenceType, schedule):
        """Validate schedule matches the recurrence type"""
        for day in schedule:
            if recurrence_type == RecurrenceType.WEEKLY:
                if day.day_of_week is None:
                    raise AvailabilityValidationError(
                        "Weekly schedule requires day_of_week to be set"
                    )
                if day.date is not None:
                    raise AvailabilityValidationError(
                        "Weekly schedule should not include specific dates"
                    )
                    
            elif recurrence_type == RecurrenceType.MONTHLY or recurrence_type == RecurrenceType.ONE_TIME:
                if day.date is None:
                    raise AvailabilityValidationError(
                        f"{recurrence_type} schedule requires specific dates"
                    )
                if day.day_of_week is not None:
                    raise AvailabilityValidationError(
                        f"{recurrence_type} schedule should not include day_of_week"
                    )

    @staticmethod
    def validate_create_availability(availability: AvailabilityCreate):
        """Validate all rules for creating availability"""
        AvailabilityValidator.validate_dates(availability.start_date, availability.end_date)
        AvailabilityValidator.validate_time_slots(availability.schedule)
        AvailabilityValidator.validate_recurrence_schedule(
            availability.recurrence_type, 
            availability.schedule
        )

    @staticmethod
    def validate_update_availability(existing_start_date: datetime, availability: AvailabilityUpdate):
        """Validate all rules for updating availability"""
        current_time = AvailabilityValidator._get_current_time()
        
        if existing_start_date < current_time:
            raise AvailabilityValidationError(
                "Cannot modify availability that has already started"
            )
            
        if availability.schedule:
            AvailabilityValidator.validate_time_slots(availability.schedule)
            
        if availability.end_date:
            AvailabilityValidator.validate_dates(existing_start_date, availability.end_date)