import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status, Path, Response
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from petstore.app.database.session import async_get_db
from petstore.app.schemas.pet import PetCreate, PetResponse, PetReplace
from petstore.app.services.pet_service import PetService
from petstore.app.core.security import async_get_current_user
from petstore.app.models.user import User # Imported for type hinting in current_user

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/", response_model=PetResponse, status_code=status.HTTP_201_CREATED, summary="Add a new pet to the store")
async def add_pet(
    pet_data: PetCreate,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(async_get_current_user) # Protected endpoint
):
    """
    Adds a new pet to the store with the provided details.
    Requires authentication.
    - **name**: Name of the pet (required, min_length=1)
    - **status**: Current status of the pet (available, pending, or sold, default: available)
    - **tags**: List of tags (optional)
    - **photo_urls**: List of photo URLs (optional)
    """
    try:
        created_pet = await PetService.async_create_pet(db, pet_data)
        return PetResponse.model_validate(created_pet)
    except SQLAlchemyError as e:
        logger.exception(f"Database error while adding pet: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Database error occurred.")
    except Exception as e:
        logger.exception(f"An unexpected error occurred while adding pet: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error.")


@router.get("/{pet_id}", response_model=PetResponse, summary="Find pet by ID")
async def get_pet_by_id(
    pet_id: int = Path(..., gt=0, description="ID of pet to return"),
    db: AsyncSession = Depends(async_get_db)
):
    """
    Returns a single pet by its ID.
    - **pet_id**: A unique integer ID for the pet. Must be greater than 0.
    """
    try:
        pet = await PetService.async_get_pet_by_id(db, pet_id)
        if not pet:
            logger.warning(f"Pet with ID {pet_id} not found or is soft-deleted.")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pet not found")
        return PetResponse.model_validate(pet)
    except SQLAlchemyError as e:
        logger.exception(f"Database error while getting pet by ID {pet_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Database error occurred.")
    except HTTPException:
        raise # Re-raise HTTPException if it's already a 404
    except Exception as e:
        logger.exception(f"An unexpected error occurred while getting pet by ID {pet_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error.")


@router.put("/", response_model=PetResponse, summary="Update an existing pet")
async def update_pet(
    pet_replace_data: PetReplace,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(async_get_current_user) # Protected endpoint
):
    """
    Updates an existing pet's information. Full replacement is expected.
    Requires authentication.
    - **id**: ID of pet to update (required)
    - **name**: Updated name of the pet (required)
    - **status**: Updated status of the pet (required)
    - **tags**: Updated list of tags (required, can be empty)
    - **photo_urls**: Updated list of photo URLs (required, can be empty)
    - **last_updated_at**: Timestamp of the last update retrieved by the client for optimistic locking (required)
    """
    try:
        updated_pet = await PetService.async_update_pet(db, pet_replace_data.id, pet_replace_data)
        return PetResponse.model_validate(updated_pet)
    except HTTPException:
        raise # Re-raise HTTPExceptions from service layer (404, 409)
    except SQLAlchemyError as e:
        logger.exception(f"Database error while updating pet ID {pet_replace_data.id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Database error occurred.")
    except Exception as e:
        logger.exception(f"An unexpected error occurred while updating pet ID {pet_replace_data.id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error.")


@router.delete("/{pet_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Deletes a pet (soft delete)")
async def delete_pet(
    pet_id: int = Path(..., gt=0, description="Pet ID to delete"),
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(async_get_current_user) # Protected endpoint
):
    """
    Soft-deletes a pet by setting its `deleted_at` timestamp.
    Requires authentication.
    - **pet_id**: The ID of the pet to be soft-deleted.
    """
    try:
        await PetService.async_delete_pet(db, pet_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except HTTPException:
        raise # Re-raise HTTPException from service layer (404)
    except SQLAlchemyError as e:
        logger.exception(f"Database error while soft-deleting pet ID {pet_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Database error occurred.")
    except Exception as e:
        logger.exception(f"An unexpected error occurred while soft-deleting pet ID {pet_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error.")