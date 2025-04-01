from pydantic import BaseModel, validator
from typing import List, Optional
from datetime import datetime, time
from backend.models.mod_availability import RecurrenceType, TimeSlot, DaySchedule

class TimeSlotCreate(BaseModel):
    start_time: time
    end_time: time
    
    @validator('end_time')
    def end_time_must_be_after_start_time(cls, v, values):
        if 'start_time' in values and v <= values['start_time']:
            raise ValueError('end_time must be after start_time')
        return v

class DayScheduleCreate(BaseModel):
    day_of_week: Optional[int] = None
    date: Optional[datetime] = None
    time_slots: List[TimeSlotCreate]
    available: bool = True

    @validator('day_of_week')
    def validate_day_of_week(cls, v):
        if v is not None and not (0 <= v <= 6):
            raise ValueError('day_of_week must be between 0 and 6')
        return v

class AvailabilityCreate(BaseModel):
    trainer_id: str
    center_id: str
    recurrence_type: RecurrenceType
    schedule: List[DayScheduleCreate]
    start_date: datetime
    end_date: Optional[datetime] = None

class AvailabilityUpdate(BaseModel):
    schedule: Optional[List[DayScheduleCreate]] = None
    end_date: Optional[datetime] = None

class AvailabilityResponse(BaseModel):
    id: str
    trainer_id: str
    center_id: str
    recurrence_type: RecurrenceType
    schedule: List[DaySchedule]
    start_date: datetime
    end_date: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True