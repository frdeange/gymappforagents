from fastapi import APIRouter, HTTPException, Depends, Query
from azure.cosmos import ContainerProxy
from backend.schemas.sch_message import (
    IndividualMessageCreate,
    MassMessageCreate,
    MessageUpdate,
    MessageResponse,
    ConversationResponse
)
from backend.services.svc_message import MessageService
from backend.models.mod_message import UserType
from backend.validators.val_message import MessageValidator
from backend.configuration.database import get_db, get_container
from backend.dependencies.dep_auth import get_current_user_id
from typing import List
from datetime import datetime

router = APIRouter(
    prefix="/messages",
    tags=["Messages"],
    responses={404: {"description": "Not found"}},
)

@router.post("/individual", response_model=MessageResponse)
def create_individual_message(
    message: IndividualMessageCreate,
    sender_type: UserType,  # TODO: Get from auth token
    db: ContainerProxy = Depends(lambda: get_container("messages")),
    sender_id: str = Depends(get_current_user_id)
):
    """
    Send an individual message to a specific user.
    
    - Users can send messages to trainers or administrators
    - Trainers can send messages to users with scheduled sessions or administrators
    - Administrators can send messages to any individual user
    """
    return MessageService.create_individual_message(db, message, sender_id, sender_type)

@router.post("/mass", response_model=MessageResponse)
def create_mass_message(
    message: MassMessageCreate,
    sender_type: UserType,  # TODO: Get from auth token
    db: ContainerProxy = Depends(lambda: get_container("messages")),
    sender_id: str = Depends(get_current_user_id)
):
    """
    Send a mass message to multiple recipients.
    
    - Only administrators can send mass messages
    - Can target multiple users or trainers
    - Cannot send mass messages to administrators
    """
    if sender_type != UserType.ADMIN:
        raise HTTPException(
            status_code=403,
            detail="Only administrators can send mass messages"
        )
    return MessageService.create_mass_message(db, message, sender_id)

@router.get("/{message_id}", response_model=MessageResponse)
def get_message(
    message_id: str,
    db: ContainerProxy = Depends(lambda: get_container("messages")),
    user_id: str = Depends(get_current_user_id)
):
    """
    Get a specific message by its ID.
    
    - User can only access messages where they are either the sender or recipient
    """
    message = MessageService.get_message(db, message_id)
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
        
    # Validate that the user has access to this message
    MessageValidator.validate_message_access(user_id, message.sender_id, message.recipient_id)
    return message

@router.get("/conversation/{user2_id}", response_model=ConversationResponse)
def get_conversation(
    user2_id: str,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: ContainerProxy = Depends(lambda: get_container("messages")),
    user1_id: str = Depends(get_current_user_id)
):
    """
    Get messages between two users.
    
    - Returns messages in chronological order (newest first)
    - Includes total message count and unread count
    - Supports pagination through limit and offset parameters
    - User can only access conversations where they are a participant
    """
    return MessageService.get_conversation(db, user1_id, user2_id, limit, offset)

@router.get("/conversations", response_model=List[MessageResponse])
def get_user_conversations(
    db: ContainerProxy = Depends(lambda: get_container("messages")),
    user_id: str = Depends(get_current_user_id)
):
    """
    Get all conversations for a user.
    
    - Returns the most recent message from each conversation
    - Conversations are ordered by most recent activity
    - Only returns conversations where the user is a participant
    """
    return MessageService.get_user_conversations(db, user_id)

@router.put("/{message_id}", response_model=MessageResponse)
def update_message(
    message_id: str,
    message: MessageUpdate,
    db: ContainerProxy = Depends(lambda: get_container("messages")),
    user_id: str = Depends(get_current_user_id)
):
    """
    Update a message's status or read timestamp.
    
    - Can only update messages where the user is the recipient
    """
    existing_message = MessageService.get_message(db, message_id)
    if not existing_message:
        raise HTTPException(status_code=404, detail="Message not found")
        
    # Only the recipient can update the message status
    if existing_message.recipient_id != user_id:
        raise HTTPException(
            status_code=403,
            detail="Only the recipient can update the message status"
        )
        
    updated = MessageService.update_message(db, message_id, message)
    return updated

@router.post("/conversation/{sender_id}/mark-read", response_model=List[MessageResponse])
def mark_conversation_as_read(
    sender_id: str,
    db: ContainerProxy = Depends(lambda: get_container("messages")),
    recipient_id: str = Depends(get_current_user_id)
):
    """
    Mark all messages in a conversation as read.
    
    - Updates status to READ and sets read_at timestamp for all unread messages
    - Only marks messages where the authenticated user is the recipient
    """
    return MessageService.mark_conversation_as_read(db, recipient_id, sender_id)

@router.delete("/{message_id}", status_code=204)
def delete_message(
    message_id: str,
    db: ContainerProxy = Depends(lambda: get_container("messages")),
    user_id: str = Depends(get_current_user_id)
):
    """
    Delete a message.
    
    - Can only delete messages where the user is either the sender or recipient
    
    Returns:
    - 204: Successfully deleted
    - 404: Message not found
    """
    message = MessageService.get_message(db, message_id)
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
        
    # Validate that the user has access to this message
    MessageValidator.validate_message_access(user_id, message.sender_id, message.recipient_id)
    
    deleted = MessageService.delete_message(db, message_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Message not found")