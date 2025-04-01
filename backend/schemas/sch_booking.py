from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class BookingCreate(BaseModel):
    user_id: str
    trainer_id: str
    center_id: str
    start_time: datetime = Field(
        description="Start time in ISO 8601 format (e.g. 2025-03-11T22:00:00.000Z)"
    )
    end_time: datetime = Field(
        description="End time in ISO 8601 format (e.g. 2025-03-11T22:00:00.000Z)"
    )
    message: Optional[str]

class BookingUpdate(BaseModel):
    start_time: Optional[datetime] = Field(
        default=None,
        description="Start time in ISO 8601 format (e.g. 2025-03-11T22:00:00.000Z)"
    )
    end_time: Optional[datetime] = Field(
        default=None,
        description="End time in ISO 8601 format (e.g. 2025-03-11T22:00:00.000Z)"
    )
    message: Optional[str] = None

class BookingResponse(BaseModel):
    id: str
    user_id: str
    trainer_id: str
    center_id: str
    start_time: datetime
    end_time: datetime
    status: str
    message: Optional[str]

    class Config:
        from_attributes = True