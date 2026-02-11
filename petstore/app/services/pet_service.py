import logging
from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from petstore.app.models.pet import Pet
from petstore.app.schemas.pet import PetCreate, PetReplace, PetResponse
from petstore.app.schemas.common import PetStatus

logger = logging.getLogger(__name__)


class PetService:
    """
    Service layer for Pet-related business logic and database operations.
    """

    @staticmethod
    async def async_create_pet(db: AsyncSession, pet_data: PetCreate) -> Pet:
        """
        Creates a new pet in the database.
        Handles default values for tags and photo_urls.
        """
        # Convert None to empty lists for tags and photo_urls if not provided
        tags = pet_data.tags if pet_data.tags is not None else []
        photo_urls = pet_data.photo_urls if pet_data.photo_urls is not None else []

        new_pet = Pet(
            name=pet_data.name,
            status=pet_data.status,
            tags=tags,
            photo_urls=photo_urls
        )
        db.add(new_pet)
        await db.commit()
        await db.refresh(new_pet)
        logger.info(f"Pet created with ID: {new_pet.id}")
        return new_pet

    @staticmethod
    async def async_get_pet_by_id(db: AsyncSession, pet_id: int) -> Pet | None:
        """
        Retrieves a pet by its ID. Filters out soft-deleted pets.
        """
        stmt = select(Pet).where(Pet.id == pet_id, Pet.deleted_at.is_(None))
        result = await db.execute(stmt)
        pet = result.scalar_one_or_none()
        return pet

    @staticmethod
    async def async_update_pet(db: AsyncSession, pet_id: int, pet_replace_data: PetReplace) -> Pet:
        """
        Updates an existing pet's details with full replacement and optimistic locking.
        """
        existing_pet = await PetService.async_get_pet_by_id(db, pet_id)

        if not existing_pet:
            logger.warning(f"Attempted to update non-existent or soft-deleted pet with ID: {pet_id}")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pet not found")

        # Optimistic locking check
        # Convert both to UTC and compare to avoid timezone issues.
        # Ensure that updated_at stored in DB is also timezone aware if possible, or naive.
        # For simplicity, assuming `func.now()` is naive or consistent, and Pydantic `datetime` is naive.
        # If DB stores timezone-aware, Pydantic needs to parse as timezone-aware.
        # A more robust solution would ensure all datetimes are UTC and timezone-aware.
        if existing_pet.updated_at.replace(microsecond=0) != pet_replace_data.last_updated_at.replace(microsecond=0):
            logger.warning(f"Optimistic locking conflict for pet ID: {pet_id}. "
                           f"DB updated_at: {existing_pet.updated_at}, Request last_updated_at: {pet_replace_data.last_updated_at}")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Pet has been modified by another process. Please retrieve the latest version and try again."
            )

        # Update all modifiable fields
        existing_pet.name = pet_replace_data.name
        existing_pet.status = pet_replace_data.status
        # Ensure lists are not None when updating
        existing_pet.tags = pet_replace_data.tags if pet_replace_data.tags is not None else []
        existing_pet.photo_urls = pet_replace_data.photo_urls if pet_replace_data.photo_urls is not None else []

        # SQLAlchemy's onupdate will handle `updated_at` automatically
        await db.commit()
        await db.refresh(existing_pet)
        logger.info(f"Pet with ID: {pet_id} updated successfully.")
        return existing_pet

    @staticmethod
    async def async_delete_pet(db: AsyncSession, pet_id: int) -> None:
        """
        Soft-deletes a pet by setting its `deleted_at` timestamp.
        """
        existing_pet = await PetService.async_get_pet_by_id(db, pet_id) # async_get_pet_by_id already filters by deleted_at.is_(None)

        if not existing_pet:
            logger.warning(f"Attempted to soft-delete non-existent or already soft-deleted pet with ID: {pet_id}")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pet not found")

        existing_pet.deleted_at = datetime.utcnow() # Set current UTC time for soft delete
        await db.commit()
        logger.info(f"Pet with ID: {pet_id} soft-deleted successfully.")

    @staticmethod
    async def async_get_pet_inventory(db: AsyncSession) -> dict[str, int]:
        """
        Calculates the live inventory count of active pets by their status.
        """
        # Get all distinct statuses, including PetStatus enum values not currently in DB
        all_statuses = {status_enum.value for status_enum in PetStatus}

        # Query to count active pets grouped by status
        stmt = select(Pet.status, func.count(Pet.id)).where(Pet.deleted_at.is_(None)).group_by(Pet.status)
        result = await db.execute(stmt)
        counts_from_db = {status.value: count for status, count in result.all()}

        # Initialize inventory with all possible statuses having a count of 0
        inventory = {status_val: 0 for status_val in all_statuses}

        # Update inventory with actual counts from the database
        inventory.update(counts_from_db)
        logger.info(f"Generated pet inventory: {inventory}")
        return inventory