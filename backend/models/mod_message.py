from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from enum import Enum

class MessageType(str, Enum):
    INDIVIDUAL = "individual"
    MASS = "mass"

class MessageStatus(str, Enum):
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"

class UserType(str, Enum):
    USER = "user"
    TRAINER = "trainer"
    ADMIN = "admin"

class Message(BaseModel):
    id: Optional[str]
    sender_id: str
    sender_type: UserType
    recipient_id: str
    recipient_type: UserType
    message_type: MessageType
    content: str
    status: MessageStatus
    created_at: datetime
    read_at: Optional[datetime]
    parent_message_id: Optional[str] = None  # For message threads/replies
    mass_recipient_ids: Optional[List[str]] = None  # For mass messages

    class Config:
        from_attributes = True