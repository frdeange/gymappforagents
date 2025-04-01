from fastapi import APIRouter, HTTPException, Depends
from azure.cosmos import ContainerProxy
from backend.schemas.sch_booking import BookingCreate, BookingUpdate, BookingResponse
from backend.services.svc_booking import BookingService
from backend.validators.val_booking import BookingValidator
from backend.configuration.database import get_db, get_container
from backend.dependencies.dep_auth import get_current_user_id, get_current_user
from typing import List

router = APIRouter(
    prefix="/bookings",
    tags=["Bookings"],
    responses={404: {"description": "Not found"}},
)

@router.post('/', response_model=BookingResponse)
def create_booking(
    booking: BookingCreate, 
    db: ContainerProxy = Depends(lambda: get_container("bookings")),
    current_user: dict = Depends(get_current_user)
):
    """
    Create a new booking for a user with a specific trainer.
    
    - Creates a booking with the specified trainer, center, time slot and optional message
    - Validates that the booking is at least 2 hours in advance
    - Returns the created booking details
    - Only the authenticated user can create bookings for themselves
    """
    # Validate that the user is creating a booking for themselves
    if booking.user_id != current_user["id"]:
        raise HTTPException(
            status_code=403,
            detail="You can only create bookings for yourself"
        )
    return BookingService.create_booking(db, booking)

@router.get('/{booking_id}', response_model=BookingResponse)
def get_booking(
    booking_id: str, 
    db: ContainerProxy = Depends(lambda: get_container("bookings")),
    current_user: dict = Depends(get_current_user)
):
    """
    Get details of a specific booking by its ID.
    - Users can only view their own bookings
    - Trainers can view bookings where they are the assigned trainer
    - Admins can view all bookings
    """
    booking = BookingService.get_booking(db, booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail='Booking not found')

    # Check access permissions
    if current_user["type"] == "admin":
        return booking
    elif current_user["type"] == "trainer" and booking.trainer_id == current_user["id"]:
        return booking
    elif current_user["type"] == "user" and booking.user_id == current_user["id"]:
        return booking
    else:
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to view this booking"
        )

@router.get('/users/{user_id}/future', response_model=List[BookingResponse])
def get_user_future_bookings(
    user_id: str, 
    db: ContainerProxy = Depends(lambda: get_container("bookings")),
    current_user: dict = Depends(get_current_user)
):
    """
    Get all future bookings for a specific user.
    
    - Returns a list of all upcoming bookings ordered by start time
    - Only includes bookings with start time after current time
    - Users can only view their own bookings
    - Trainers can view bookings of their assigned users
    - Admins can view all bookings
    """
    # Check access permissions
    if current_user["type"] != "admin":
        if current_user["id"] != user_id:
            raise HTTPException(
                status_code=403,
                detail="You can only view your own bookings"
            )
    return BookingService.get_user_future_bookings(db, user_id)

@router.get('/users/{user_id}/past', response_model=List[BookingResponse])
def get_user_past_bookings(
    user_id: str, 
    db: ContainerProxy = Depends(lambda: get_container("bookings")),
    current_user: dict = Depends(get_current_user)
):
    """
    Get all past bookings for a specific user.
    
    - Returns a list of all past bookings ordered by start time in descending order
    - Only includes bookings with start time before current time
    - Users can only view their own bookings
    - Trainers can view bookings of their assigned users
    - Admins can view all bookings
    """
    # Check access permissions
    if current_user["type"] != "admin":
        if current_user["id"] != user_id:
            raise HTTPException(
                status_code=403,
                detail="You can only view your own bookings"
            )
    return BookingService.get_user_past_bookings(db, user_id)

@router.put('/{booking_id}', response_model=BookingResponse)
def update_booking(
    booking_id: str, 
    booking: BookingUpdate, 
    db: ContainerProxy = Depends(lambda: get_container("bookings")),
    current_user: dict = Depends(get_current_user)
):
    """
    Update an existing booking.
    
    - Can modify start time, end time and/or message
    - Validates that changes are made at least 24 hours before the booking
    - Records all modifications in the booking history
    - Users can only update their own bookings
    - Trainers can update bookings where they are the assigned trainer
    - Admins can update any booking
    """
    existing_booking = BookingService.get_booking(db, booking_id)
    if not existing_booking:
        raise HTTPException(status_code=404, detail='Booking not found')

    # Check update permissions
    if current_user["type"] == "admin":
        pass  # Admins can update any booking
    elif current_user["type"] == "trainer" and existing_booking.trainer_id == current_user["id"]:
        pass  # Trainers can update their own bookings
    elif current_user["type"] == "user" and existing_booking.user_id == current_user["id"]:
        pass  # Users can update their own bookings
    else:
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to update this booking"
        )

    updated_booking = BookingService.update_booking(db, booking_id, booking)
    return updated_booking

@router.post('/{booking_id}/cancel', response_model=BookingResponse)
def cancel_booking(
    booking_id: str, 
    db: ContainerProxy = Depends(lambda: get_container("bookings")),
    current_user: dict = Depends(get_current_user)
):
    """
    Cancel an existing booking.
    
    - Changes booking status to 'cancelled'
    - Can only cancel bookings at least 24 hours in advance
    - Records cancellation in the booking history
    - Users can only cancel their own bookings
    - Trainers can cancel bookings where they are the assigned trainer
    - Admins can cancel any booking
    """
    existing_booking = BookingService.get_booking(db, booking_id)
    if not existing_booking:
        raise HTTPException(status_code=404, detail='Booking not found')

    # Check cancellation permissions
    if current_user["type"] == "admin":
        pass  # Admins can cancel any booking
    elif current_user["type"] == "trainer" and existing_booking.trainer_id == current_user["id"]:
        pass  # Trainers can cancel their own bookings
    elif current_user["type"] == "user" and existing_booking.user_id == current_user["id"]:
        pass  # Users can cancel their own bookings
    else:
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to cancel this booking"
        )

    cancelled_booking = BookingService.cancel_booking(db, booking_id)
    return cancelled_booking