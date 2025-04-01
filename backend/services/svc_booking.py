from azure.cosmos import ContainerProxy
from backend.models.mod_booking import Booking, BookingChange
from backend.schemas.sch_booking import BookingCreate, BookingUpdate
from backend.validators.val_booking import BookingValidator
import uuid
from datetime import datetime, timezone

class BookingService:
    @staticmethod
    def create_booking(db: ContainerProxy, booking: BookingCreate) -> Booking:
        # Validate business rules
        BookingValidator.validate_create_booking(booking)
        
        booking_id = str(uuid.uuid4())
        booking_dict = {
            "id": booking_id,
            "user_id": booking.user_id,
            "trainer_id": booking.trainer_id,
            "center_id": booking.center_id,
            "start_time": booking.start_time.replace(tzinfo=timezone.utc).isoformat(),
            "end_time": booking.end_time.replace(tzinfo=timezone.utc).isoformat(),
            "status": "booked",
            "message": booking.message,
            "changes": []
        }
        
        db.create_item(body=booking_dict)
        
        # Convert dates back to datetime for the return object
        booking_dict["start_time"] = booking.start_time.replace(tzinfo=timezone.utc)
        booking_dict["end_time"] = booking.end_time.replace(tzinfo=timezone.utc)
        return Booking(**booking_dict)

    @staticmethod
    def get_booking(db: ContainerProxy, booking_id: str) -> Booking:
        query = f'SELECT * FROM c WHERE c.id = "{booking_id}"'
        items = list(db.query_items(query=query, enable_cross_partition_query=True))
        if items:
            item = items[0]
            # Convert dates from string to datetime
            item["start_time"] = datetime.fromisoformat(item["start_time"])
            item["end_time"] = datetime.fromisoformat(item["end_time"])
            # Convert change timestamps if they exist
            if "changes" in item:
                for change in item["changes"]:
                    change["timestamp"] = datetime.fromisoformat(change["timestamp"])
                    if change.get("previous_start_time"):
                        change["previous_start_time"] = datetime.fromisoformat(change["previous_start_time"])
                    if change.get("previous_end_time"):
                        change["previous_end_time"] = datetime.fromisoformat(change["previous_end_time"])
            return Booking(**item)
        return None

    @staticmethod
    def get_user_future_bookings(db: ContainerProxy, user_id: str) -> list[Booking]:
        """Get all future bookings for a specific user"""
        current_time = datetime.now(timezone.utc).isoformat()
        query = f'SELECT * FROM c WHERE c.user_id = "{user_id}" AND c.start_time > "{current_time}" ORDER BY c.start_time ASC'
        
        items = list(db.query_items(query=query, enable_cross_partition_query=False))
        bookings = []
        
        for item in items:
            # Convert dates from string to datetime
            item["start_time"] = datetime.fromisoformat(item["start_time"])
            item["end_time"] = datetime.fromisoformat(item["end_time"])
            if "changes" in item:
                for change in item["changes"]:
                    change["timestamp"] = datetime.fromisoformat(change["timestamp"])
                    if change.get("previous_start_time"):
                        change["previous_start_time"] = datetime.fromisoformat(change["previous_start_time"])
                    if change.get("previous_end_time"):
                        change["previous_end_time"] = datetime.fromisoformat(change["previous_end_time"])
            bookings.append(Booking(**item))
            
        return bookings

    @staticmethod
    def get_user_past_bookings(db: ContainerProxy, user_id: str) -> list[Booking]:
        """Get all past bookings for a specific user"""
        current_time = datetime.now(timezone.utc).isoformat()
        query = f'SELECT * FROM c WHERE c.user_id = "{user_id}" AND c.start_time < "{current_time}" ORDER BY c.start_time DESC'
        
        items = list(db.query_items(query=query, enable_cross_partition_query=False))
        bookings = []
        
        for item in items:
            # Convert dates from string to datetime
            item["start_time"] = datetime.fromisoformat(item["start_time"])
            item["end_time"] = datetime.fromisoformat(item["end_time"])
            if "changes" in item:
                for change in item["changes"]:
                    change["timestamp"] = datetime.fromisoformat(change["timestamp"])
                    if change.get("previous_start_time"):
                        change["previous_start_time"] = datetime.fromisoformat(change["previous_start_time"])
                    if change.get("previous_end_time"):
                        change["previous_end_time"] = datetime.fromisoformat(change["previous_end_time"])
            bookings.append(Booking(**item))
            
        return bookings

    @staticmethod
    def update_booking(db: ContainerProxy, booking_id: str, booking: BookingUpdate) -> Booking:
        existing_booking = BookingService.get_booking(db, booking_id)
        if existing_booking:
            # Only proceed if there are actual changes to dates or message
            has_changes = any([
                booking.start_time and booking.start_time != existing_booking.start_time,
                booking.end_time and booking.end_time != existing_booking.end_time,
                booking.message != existing_booking.message
            ])

            if has_changes:
                # Validate business rules
                BookingValidator.validate_update_booking(existing_booking.start_time, booking)
                
                # Create change record
                change = BookingChange(
                    timestamp=datetime.now(timezone.utc),
                    change_type="modification",
                    previous_start_time=existing_booking.start_time,
                    previous_end_time=existing_booking.end_time
                )
                
                if booking.start_time:
                    existing_booking.start_time = booking.start_time.replace(tzinfo=timezone.utc)
                if booking.end_time:
                    existing_booking.end_time = booking.end_time.replace(tzinfo=timezone.utc)
                if booking.message is not None:  # Allow empty string messages
                    existing_booking.message = booking.message
                
                # Add change record
                existing_booking.changes.append(change)
                
                # Convert to dictionary and dates to string for storage
                booking_dict = existing_booking.dict()
                booking_dict["start_time"] = existing_booking.start_time.isoformat()
                booking_dict["end_time"] = existing_booking.end_time.isoformat()
                
                # Convert changes timestamps to ISO format
                for change_dict in booking_dict["changes"]:
                    change_dict["timestamp"] = change_dict["timestamp"].isoformat()
                    if change_dict.get("previous_start_time"):
                        change_dict["previous_start_time"] = change_dict["previous_start_time"].isoformat()
                    if change_dict.get("previous_end_time"):
                        change_dict["previous_end_time"] = change_dict["previous_end_time"].isoformat()
                
                db.upsert_item(body=booking_dict)
            
        return existing_booking

    @staticmethod
    def cancel_booking(db: ContainerProxy, booking_id: str) -> Booking:
        """Cancel a booking by changing its status to 'cancelled'"""
        existing_booking = BookingService.get_booking(db, booking_id)
        if existing_booking:
            # Validate business rules for cancellation
            BookingValidator.validate_cancel_booking(existing_booking.start_time)
            
            # Create cancellation record
            change = BookingChange(
                timestamp=datetime.now(timezone.utc),
                change_type="cancellation"
            )
            existing_booking.changes.append(change)
            
            # Update status
            existing_booking.status = "cancelled"
            
            # Convert to dictionary and dates to string for storage
            booking_dict = existing_booking.dict()
            booking_dict["start_time"] = existing_booking.start_time.isoformat()
            booking_dict["end_time"] = existing_booking.end_time.isoformat()
            
            # Convert changes timestamps to ISO format
            for change_dict in booking_dict["changes"]:
                change_dict["timestamp"] = change_dict["timestamp"].isoformat()
                if change_dict.get("previous_start_time"):
                    change_dict["previous_start_time"] = change_dict["previous_start_time"].isoformat()
                if change_dict.get("previous_end_time"):
                    change_dict["previous_end_time"] = change_dict["previous_end_time"].isoformat()
            
            db.upsert_item(body=booking_dict)
            
        return existing_booking