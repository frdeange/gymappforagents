from azure.cosmos import ContainerProxy
from backend.models.mod_message import Message, MessageType, MessageStatus, UserType
from backend.schemas.sch_message import IndividualMessageCreate, MassMessageCreate, MessageUpdate, ConversationResponse
from backend.validators.val_message import MessageValidator, MessageValidationError
import uuid
from datetime import datetime, timezone
from typing import List, Optional

class MessageService:
    @staticmethod
    def create_individual_message(
        db: ContainerProxy, 
        message: IndividualMessageCreate, 
        sender_id: str,
        sender_type: UserType
    ) -> Message:
        """Create a new individual message"""
        # Validate business rules
        MessageValidator.validate_create_individual_message(sender_type, message)
        
        current_time = datetime.now(timezone.utc)
        message_id = str(uuid.uuid4())
        
        message_dict = {
            "id": message_id,
            "sender_id": sender_id,
            "sender_type": sender_type,
            "recipient_id": message.recipient_id,
            "recipient_type": message.recipient_type,
            "message_type": MessageType.INDIVIDUAL,
            "content": message.content,
            "status": MessageStatus.SENT,
            "created_at": current_time.isoformat(),
            "read_at": None,
            "parent_message_id": message.parent_message_id,
            "mass_recipient_ids": None
        }
        
        db.create_item(body=message_dict)
        
        # Convert dates back to datetime for the return object
        message_dict["created_at"] = current_time
        return Message(**message_dict)

    @staticmethod
    def create_mass_message(
        db: ContainerProxy, 
        message: MassMessageCreate, 
        sender_id: str
    ) -> Message:
        """Create a new mass message"""
        current_time = datetime.now(timezone.utc)
        reference_message = None
        
        # Create a message for each recipient
        for recipient_id in message.recipient_ids:
            message_dict = {
                "id": str(uuid.uuid4()),
                "sender_id": sender_id,
                "sender_type": UserType.ADMIN,
                "recipient_id": recipient_id,
                "recipient_type": message.recipient_type,
                "message_type": MessageType.MASS,
                "content": message.content,
                "status": MessageStatus.SENT,
                "created_at": current_time.isoformat(),
                "read_at": None,
                "parent_message_id": None,
                "mass_recipient_ids": message.recipient_ids
            }
            
            db.create_item(body=message_dict)
            
            # Keep the first message as reference
            if reference_message is None:
                # Convert dates for the reference message that will be returned
                message_dict["created_at"] = current_time
                reference_message = Message(**message_dict)
        
        if reference_message is None:
            raise MessageValidationError("No messages were created")
            
        return reference_message

    @staticmethod
    def get_message(db: ContainerProxy, message_id: str) -> Optional[Message]:
        """Get a specific message by ID"""
        query = f'SELECT * FROM c WHERE c.id = "{message_id}"'
        items = list(db.query_items(query=query, enable_cross_partition_query=True))
        
        if items:
            item = items[0]
            # Convert dates from string to datetime
            item["created_at"] = datetime.fromisoformat(item["created_at"])
            if item["read_at"]:
                item["read_at"] = datetime.fromisoformat(item["read_at"])
            return Message(**item)
        return None

    @staticmethod
    def get_conversation(
        db: ContainerProxy, 
        user1_id: str, 
        user2_id: str, 
        limit: int = 50, 
        offset: int = 0
    ) -> ConversationResponse:
        """Get messages between two users"""
        # Get messages for the conversation
        query = f'''
        SELECT * FROM c 
        WHERE (
            (c.sender_id = "{user1_id}" AND c.recipient_id = "{user2_id}") OR 
            (c.sender_id = "{user2_id}" AND c.recipient_id = "{user1_id}")
        )
        AND c.message_type = "individual"
        ORDER BY c.created_at DESC
        OFFSET {offset} LIMIT {limit}
        '''
        
        items = list(db.query_items(query=query, enable_cross_partition_query=True))
        messages = []
        
        for item in items:
            # Convert dates from string to datetime
            item["created_at"] = datetime.fromisoformat(item["created_at"])
            if item["read_at"]:
                item["read_at"] = datetime.fromisoformat(item["read_at"])
            messages.append(Message(**item))
        
        # Count unread messages using a separate query with VALUE
        unread_query = f'''
        SELECT VALUE COUNT(1) FROM c 
        WHERE c.recipient_id = "{user1_id}" 
        AND c.sender_id = "{user2_id}"
        AND (c.read_at = null OR c.status != "read")
        '''
        unread_count = list(db.query_items(query=unread_query, enable_cross_partition_query=True))[0]
        
        # Get total messages count using a separate query with VALUE
        total_query = f'''
        SELECT VALUE COUNT(1) FROM c 
        WHERE (
            (c.sender_id = "{user1_id}" AND c.recipient_id = "{user2_id}") OR 
            (c.sender_id = "{user2_id}" AND c.recipient_id = "{user1_id}")
        )
        AND c.message_type = "individual"
        '''
        total_messages = list(db.query_items(query=total_query, enable_cross_partition_query=True))[0]
        
        return ConversationResponse(
            messages=messages,
            total_messages=total_messages,
            unread_count=unread_count
        )

    @staticmethod
    def get_user_conversations(db: ContainerProxy, user_id: str) -> List[Message]:
        """Get the last message from each conversation the user is involved in"""
        query = f'''
        SELECT * FROM c 
        WHERE c.id IN (
            SELECT VALUE MAX(t.id)
            FROM t
            WHERE (t.sender_id = "{user_id}" OR t.recipient_id = "{user_id}")
            AND t.message_type = "{MessageType.INDIVIDUAL}"
            GROUP BY 
                CASE 
                    WHEN t.sender_id = "{user_id}" THEN t.recipient_id 
                    ELSE t.sender_id 
                END
        )
        ORDER BY c.created_at DESC
        '''
        
        items = list(db.query_items(query=query, enable_cross_partition_query=True))
        messages = []
        
        for item in items:
            # Convert dates from string to datetime
            item["created_at"] = datetime.fromisoformat(item["created_at"])
            if item["read_at"]:
                item["read_at"] = datetime.fromisoformat(item["read_at"])
            messages.append(Message(**item))
            
        return messages

    @staticmethod
    def update_message(db: ContainerProxy, message_id: str, update: MessageUpdate) -> Optional[Message]:
        """Update a message's status or read timestamp"""
        existing_message = MessageService.get_message(db, message_id)
        if existing_message:
            # Validate update
            MessageValidator.validate_update_message(update)
            
            # Update fields
            if update.status is not None:
                existing_message.status = update.status
            if update.read_at is not None:
                existing_message.read_at = update.read_at.replace(tzinfo=timezone.utc)
            
            # Convert to dictionary and serialize dates for storage
            message_dict = existing_message.dict()
            message_dict["created_at"] = existing_message.created_at.isoformat()
            message_dict["read_at"] = existing_message.read_at.isoformat() if existing_message.read_at else None
            
            db.upsert_item(body=message_dict)
            return existing_message
            
        return None

    @staticmethod
    def mark_conversation_as_read(
        db: ContainerProxy, 
        recipient_id: str, 
        sender_id: str
    ) -> List[Message]:
        """Mark all messages in a conversation as read"""
        current_time = datetime.now(timezone.utc)
        
        query = f'''
        SELECT * FROM c 
        WHERE c.recipient_id = "{recipient_id}" 
        AND c.sender_id = "{sender_id}"
        AND (c.read_at = null OR c.status != "{MessageStatus.READ}")
        '''
        
        items = list(db.query_items(query=query, enable_cross_partition_query=True))
        updated_messages = []
        
        for item in items:
            item["status"] = MessageStatus.READ
            item["read_at"] = current_time.isoformat()
            db.upsert_item(body=item)
            
            # Convert dates from string to datetime for return
            item["created_at"] = datetime.fromisoformat(item["created_at"])
            item["read_at"] = current_time
            updated_messages.append(Message(**item))
            
        return updated_messages

    @staticmethod
    def delete_message(db: ContainerProxy, message_id: str) -> bool:
        """Delete a message"""
        try:
            db.delete_item(item=message_id, partition_key=message_id)
            return True
        except Exception:
            return False