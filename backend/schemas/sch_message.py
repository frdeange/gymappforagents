from pydantic import BaseModel, validator
from typing import Optional, List
from datetime import datetime
from backend.models.mod_message import MessageType, MessageStatus, UserType

class IndividualMessageCreate(BaseModel):
    recipient_id: str
    recipient_type: UserType
    content: str
    parent_message_id: Optional[str] = None

class MassMessageCreate(BaseModel):
    recipient_type: UserType
    content: str
    recipient_ids: List[str]

    @validator('recipient_type')
    def validate_recipient_type(cls, v):
        if v == UserType.ADMIN:
            raise ValueError('Cannot send mass messages to administrators')
        return v

class MessageUpdate(BaseModel):
    status: Optional[MessageStatus]
    read_at: Optional[datetime]

class MessageResponse(BaseModel):
    id: str
    sender_id: str
    sender_type: UserType
    recipient_id: str
    recipient_type: UserType
    message_type: MessageType
    content: str
    status: MessageStatus
    created_at: datetime
    read_at: Optional[datetime]
    parent_message_id: Optional[str]

    class Config:
        from_attributes = True

class ConversationResponse(BaseModel):
    messages: List[MessageResponse]
    total_messages: int
    unread_count: int