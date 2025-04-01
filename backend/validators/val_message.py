from datetime import datetime
from fastapi import HTTPException
from backend.schemas.sch_message import IndividualMessageCreate, MassMessageCreate, MessageUpdate
from backend.models.mod_message import MessageType, UserType

class MessageValidationError(HTTPException):
    def __init__(self, detail: str):
        super().__init__(status_code=400, detail=detail)

class MessageForbiddenError(HTTPException):
    def __init__(self, detail: str):
        super().__init__(status_code=403, detail=detail)

class MessageValidator:
    @staticmethod
    def validate_conversation_access(requesting_user_id: str, participant_id: str):
        """Validate that the requesting user is a participant in the conversation"""
        if requesting_user_id != participant_id:
            raise MessageForbiddenError(
                "You can only access conversations where you are a participant"
            )

    @staticmethod
    def validate_message_access(requesting_user_id: str, message_sender_id: str, message_recipient_id: str):
        """Validate that the requesting user is either the sender or recipient of the message"""
        if requesting_user_id not in [message_sender_id, message_recipient_id]:
            raise MessageForbiddenError(
                "You can only access messages where you are either the sender or recipient"
            )

    @staticmethod
    def validate_individual_permissions(sender_type: UserType, recipient_type: UserType):
        """Validate that the sender has permission to send to this type of recipient"""
        if sender_type == UserType.USER:
            if recipient_type not in [UserType.TRAINER, UserType.ADMIN]:
                raise MessageValidationError(
                    "Users can only send messages to trainers or administrators"
                )
        elif sender_type == UserType.TRAINER:
            if recipient_type not in [UserType.USER, UserType.ADMIN]:
                raise MessageValidationError(
                    "Trainers can only send messages to users or administrators"
                )
        # Admins can send to anyone, so no validation needed

    @staticmethod
    def validate_trainer_user_relationship(trainer_id: str, user_id: str, db):
        """
        Validate that a trainer has an active relationship with a user
        (i.e., past or future bookings)
        """
        # TODO: Implement actual booking check
        # This would need to check if there are any bookings between the trainer and user
        pass

    @staticmethod
    def validate_create_individual_message(sender_type: UserType, message: IndividualMessageCreate):
        """Validate all rules for creating an individual message"""
        MessageValidator.validate_individual_permissions(sender_type, message.recipient_type)
        
        # Validate content is not empty
        if not message.content.strip():
            raise MessageValidationError(
                "Message content cannot be empty"
            )

    @staticmethod
    def validate_create_mass_message(message: MassMessageCreate):
        """Validate all rules for creating a mass message"""
        # Validate content is not empty
        if not message.content.strip():
            raise MessageValidationError(
                "Message content cannot be empty"
            )
            
        # Validate recipient list is not empty
        if not message.recipient_ids:
            raise MessageValidationError(
                "Mass message must have at least one recipient"
            )
            
        # Validate recipient type
        if message.recipient_type == UserType.ADMIN:
            raise MessageValidationError(
                "Cannot send mass messages to administrators"
            )

    @staticmethod
    def validate_update_message(message_update: MessageUpdate):
        """Validate all rules for updating a message"""
        # Currently only supports updating status and read timestamp
        if message_update.status is None and message_update.read_at is None:
            raise MessageValidationError(
                "At least one field must be updated"
            )