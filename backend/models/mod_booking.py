from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timezone

class BookingChange(BaseModel):
    timestamp: datetime
    change_type: str  # 'modification' or 'cancellation'
    previous_start_time: Optional[datetime] = None
    previous_end_time: Optional[datetime] = None

class Booking(BaseModel):
    id: Optional[str]
    user_id: str
    trainer_id: str
    center_id: str
    start_time: datetime
    end_time: datetime
    status: str
    message: Optional[str]
    changes: List[BookingChange] = []

    class Config:
        from_attributes = True