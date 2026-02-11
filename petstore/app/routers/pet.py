import logging
from typing import List
from fastapi import APIRouter, Depends, status, HTTPException

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import NotFoundException, ConflictException, AppException
from app.schemas.pet import PetCreate, PetUpdate, PetResponse
from app.services.pet import PetService

router = APIRouter(
    prefix="/pet",
    tags=["pet"],
    responses={
        400: {"description": "Invalid ID supplied"},
        404: {"description": "Pet not found"},
        422: {"description": "Validation Error"}
    },
)

logger = logging.getLogger(__name__)

# Instantiate service (can be a dependency if more complex)
pet_service = PetService()

@router.post(
    "/",
    response_model=PetResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a new pet to the store",
    description="Adds a new pet to the store with the provided details. The ID is automatically generated.",
    responses={
        201: {"description": "Pet created successfully"},
        405: {"description": "Invalid input"}
    }
)
async def add_pet(
    pet_data: PetCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Adds a new pet to the store.
    """
    logger.info(f"Received request to add a new pet: {pet_data.model_dump_json()}")
    try:
        created_pet = await pet_service.create_pet(db, pet_data)
        return PetResponse.model_validate(created_pet)
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    except Exception as e:
        logger.error(f"Unexpected error when adding pet: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An unexpected error occurred.")

@router.get(
    "/{pet_id}",
    response_model=PetResponse,
    status_code=status.HTTP_200_OK,
    summary="Find pet by ID",
    description="Returns a single pet based on its unique ID.",
    responses={
        200: {"description": "Successful operation"},
        400: {"description": "Invalid ID supplied"},
        404: {"description": "Pet not found"}
    }
)
async def get_pet_by_id(
    pet_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Finds a pet by its unique ID.
    """
    logger.info(f"Received request to get pet by ID: {pet_id}")
    if pet_id <= 0:
        logger.warning(f"Invalid pet ID supplied: {pet_id}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid ID supplied")
    
    pet = await pet_service.get_pet(db, pet_id)
    if not pet:
        logger.warning(f"Pet with ID {pet_id} not found.")
        raise NotFoundException(detail=f"Pet with ID {pet_id} not found.")
    
    return PetResponse.model_validate(pet)

@router.put(
    "/",
    response_model=PetResponse,
    status_code=status.HTTP_200_OK,
    summary="Update an existing pet",
    description="Updates an existing pet in the store. The entire pet object must be provided, including its ID.",
    responses={
        200: {"description": "Successful operation"},
        400: {"description": "Invalid ID supplied"},
        404: {"description": "Pet not found"},
        405: {"description": "Validation exception"}
    }
)
async def update_pet(
    pet_data: PetUpdate, # PetUpdate now includes the 'id' field
    db: AsyncSession = Depends(get_db)
):
    """
    Updates an existing pet.
    """
    logger.info(f"Received request to update pet with ID: {pet_data.id}. Data: {pet_data.model_dump_json()}")
    if pet_data.id <= 0:
        logger.warning(f"Invalid pet ID supplied in update request: {pet_data.id}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid ID supplied")

    updated_pet = await pet_service.update_pet(db, pet_data.id, pet_data)
    if not updated_pet:
        logger.warning(f"Pet with ID {pet_data.id} not found for update.")
        raise NotFoundException(detail=f"Pet with ID {pet_data.id} not found.")
    
    return PetResponse.model_validate(updated_pet)

@router.delete(
    "/{pet_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Deletes a pet",
    description="Soft-deletes a pet from the store by its ID. It sets the `is_deleted` flag to true.",
    responses={
        204: {"description": "Pet soft-deleted successfully"},
        400: {"description": "Invalid ID supplied"},
        404: {"description": "Pet not found"}
    }
)
async def delete_pet(
    pet_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Soft-deletes a pet by ID.
    """
    logger.info(f"Received request to delete pet with ID: {pet_id}")
    if pet_id <= 0:
        logger.warning(f"Invalid pet ID supplied for deletion: {pet_id}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid ID supplied")
    
    deleted_pet = await pet_service.delete_pet(db, pet_id)
    if not deleted_pet:
        logger.warning(f"Pet with ID {pet_id} not found for deletion.")
        raise NotFoundException(detail=f"Pet with ID {pet_id} not found.")
    
    return # 204 No Content response