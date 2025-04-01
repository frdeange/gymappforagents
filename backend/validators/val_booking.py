from datetime import datetime, timedelta, timezone
from fastapi import HTTPException
from backend.schemas.sch_booking import BookingCreate, BookingUpdate

class BookingValidationError(HTTPException):
    def __init__(self, detail: str):
        super().__init__(status_code=400, detail=detail)

class BookingValidator:
    @staticmethod
    def _get_current_time():
        """Get current time as UTC timezone-aware datetime"""
        return datetime.now(timezone.utc)

    @staticmethod
    def validate_future_booking(start_time: datetime):
        """Validate that a booking is not too close to current time"""
        min_hours = 2
        current_time = BookingValidator._get_current_time()
        if current_time + timedelta(hours=min_hours) > start_time.replace(tzinfo=timezone.utc):
            raise BookingValidationError(
                f"Bookings must be made at least {min_hours} hours in advance"
            )

    @staticmethod
    def validate_booking_modification(booking_time: datetime):
        """Validate that a booking can be modified (24h before)"""
        current_time = BookingValidator._get_current_time()
        if current_time + timedelta(hours=24) > booking_time.replace(tzinfo=timezone.utc):
            raise BookingValidationError(
                "Bookings can only be modified at least 24 hours in advance"
            )

    @staticmethod
    def validate_past_booking(booking_time: datetime):
        """Validate that a booking is not in the past"""
        current_time = BookingValidator._get_current_time()
        if current_time > booking_time.replace(tzinfo=timezone.utc):
            raise BookingValidationError(
                "Past bookings cannot be modified"
            )

    @staticmethod
    def validate_create_booking(booking: BookingCreate):
        """Validate all rules for creating a booking"""
        BookingValidator.validate_future_booking(booking.start_time)

    @staticmethod
    def validate_update_booking(existing_start_time: datetime, booking: BookingUpdate):
        """Validate all rules for updating a booking"""
        BookingValidator.validate_past_booking(existing_start_time)
        BookingValidator.validate_booking_modification(existing_start_time)
        if booking.start_time:
            BookingValidator.validate_future_booking(booking.start_time)

    @staticmethod
    def validate_cancel_booking(booking_time: datetime):
        """Validate all rules for canceling a booking"""
        BookingValidator.validate_past_booking(booking_time)
        BookingValidator.validate_booking_modification(booking_time)