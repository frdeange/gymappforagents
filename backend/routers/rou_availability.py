from fastapi import APIRouter, HTTPException, Depends, Query
from azure.cosmos import ContainerProxy
from backend.schemas.sch_availability import (
    AvailabilityCreate, 
    AvailabilityUpdate, 
    AvailabilityResponse
)
from backend.services.svc_availability import AvailabilityService
from backend.configuration.database import get_db, get_container
from backend.dependencies.dep_auth import get_current_user
from typing import List
from datetime import datetime

router = APIRouter(
    prefix="/availabilities",
    tags=["Availabilities"],
    responses={404: {"description": "Not found"}},
)

@router.post("/", response_model=AvailabilityResponse)
def create_availability(
    availability: AvailabilityCreate,
    db: ContainerProxy = Depends(lambda: get_container("availabilities")),
    current_user: dict = Depends(get_current_user)
):
    """
    Create a new availability schedule for a trainer at a specific center.
    
    - Supports daily, weekly, monthly, and one-time schedules
    - Validates that time slots don't overlap
    - Only trainers can create their own availability
    - Admins can create availability for any trainer
    """
    # Validate permissions
    if current_user["type"] not in ["admin", "trainer"]:
        raise HTTPException(
            status_code=403,
            detail="Only trainers and administrators can create availability schedules"
        )
    
    # If trainer, validate they're creating their own availability
    if current_user["type"] == "trainer" and availability.trainer_id != current_user["id"]:
        raise HTTPException(
            status_code=403,
            detail="Trainers can only create their own availability schedules"
        )
        
    return AvailabilityService.create_availability(db, availability)

@router.get("/{availability_id}", response_model=AvailabilityResponse)
def get_availability(
    availability_id: str,
    db: ContainerProxy = Depends(lambda: get_container("availabilities")),
    current_user: dict = Depends(get_current_user)
):
    """
    Get a specific availability schedule by its ID.
    """
    availability = AvailabilityService.get_availability(db, availability_id)
    if not availability:
        raise HTTPException(status_code=404, detail="Availability not found")

    # Check permissions
    if current_user["type"] == "admin":
        return availability
    elif current_user["type"] == "trainer" and availability.trainer_id == current_user["id"]:
        return availability
    else:
        # Users can view any trainer's availability
        return availability

@router.get("/trainer/{trainer_id}", response_model=List[AvailabilityResponse])
def get_trainer_availabilities(
    trainer_id: str,
    db: ContainerProxy = Depends(lambda: get_container("availabilities")),
    current_user: dict = Depends(get_current_user)
):
    """
    Get all availability schedules for a specific trainer.
    """
    return AvailabilityService.get_trainer_availabilities(db, trainer_id)

@router.get("/center/{center_id}", response_model=List[AvailabilityResponse])
def get_center_availabilities(
    center_id: str,
    start_date: datetime = Query(..., description="Start date to search for availabilities"),
    end_date: datetime = Query(..., description="End date to search for availabilities"),
    db: ContainerProxy = Depends(lambda: get_container("availabilities"))
):
    """
    Get all availabilities for a specific center within a date range.
    
    - Returns all trainer availabilities for the specified center
    - Filters by the provided date range
    - Includes recurring and one-time schedules
    """
    return AvailabilityService.get_center_availabilities(db, center_id, start_date, end_date)

@router.put("/{availability_id}", response_model=AvailabilityResponse)
def update_availability(
    availability_id: str,
    availability: AvailabilityUpdate,
    db: ContainerProxy = Depends(lambda: get_container("availabilities")),
    current_user: dict = Depends(get_current_user)
):
    """
    Update an existing availability schedule.
    
    - Can modify schedule and end date
    - Cannot modify past availability periods
    - Only trainers can update their own availability
    - Admins can update any trainer's availability
    """
    existing = AvailabilityService.get_availability(db, availability_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Availability not found")

    # Check permissions
    if current_user["type"] == "admin":
        pass  # Admins can update any availability
    elif current_user["type"] == "trainer" and existing.trainer_id == current_user["id"]:
        pass  # Trainers can update their own availability
    else:
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to update this availability schedule"
        )

    updated = AvailabilityService.update_availability(db, availability_id, availability)
    return updated

@router.delete("/{availability_id}", status_code=204)
def delete_availability(
    availability_id: str,
    db: ContainerProxy = Depends(lambda: get_container("availabilities")),
    current_user: dict = Depends(get_current_user)
):
    """
    Delete an availability schedule.
    
    - Only trainers can delete their own availability
    - Admins can delete any trainer's availability
    
    Returns:
    - 204: Successfully deleted
    - 404: Availability not found
    """
    existing = AvailabilityService.get_availability(db, availability_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Availability not found")

    # Check permissions
    if current_user["type"] == "admin":
        pass  # Admins can delete any availability
    elif current_user["type"] == "trainer" and existing.trainer_id == current_user["id"]:
        pass  # Trainers can delete their own availability
    else:
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to delete this availability schedule"
        )

    deleted = AvailabilityService.delete_availability(db, availability_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Availability not found")