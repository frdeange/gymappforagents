from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, time
from enum import Enum

class RecurrenceType(str, Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    ONE_TIME = "one_time"

class TimeSlot(BaseModel):
    start_time: time
    end_time: time

class DaySchedule(BaseModel):
    day_of_week: Optional[int] = None  # 0-6 for weekly schedule, None for one_time
    date: Optional[datetime] = None     # Specific date for one_time or monthly schedule
    time_slots: List[TimeSlot]
    available: bool = True              # False for marking days off

class Availability(BaseModel):
    id: Optional[str]
    trainer_id: str
    center_id: str
    recurrence_type: RecurrenceType
    schedule: List[DaySchedule]
    start_date: datetime                # When this availability pattern starts
    end_date: Optional[datetime]        # Optional end date for the pattern
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True