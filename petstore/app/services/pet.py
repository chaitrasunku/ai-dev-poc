import logging
from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.database import models
from app.schemas.pet import PetCreate, PetUpdate, PetStatusEnum
from app.core.exceptions import NotFoundException, ConflictException, AppException

logger = logging.getLogger(__name__)

class PetService:
    """
    Service layer for Pet operations.
    Encapsulates business logic and interacts with the database.
    """

    async def create_pet(self, db: AsyncSession, pet_data: PetCreate) -> models.Pet:
        """
        Creates a new pet in the database.
        Args:
            db (AsyncSession): The database session.
            pet_data (PetCreate): The data for the new pet.
        Returns:
            models.Pet: The created pet ORM object.
        """
        try:
            db_pet = models.Pet(
                name=pet_data.name,
                status=pet_data.status.value, # Store enum value as string
                tags=pet_data.tags,
                photo_urls=pet_data.photoUrls,
                is_deleted=False
            )
            db.add(db_pet)
            await db.commit()
            await db.refresh(db_pet)
            logger.info(f"Pet created with ID: {db_pet.id}")
            return db_pet
        except Exception as e:
            logger.error(f"Error creating pet: {e}", exc_info=True)
            await db.rollback()
            raise AppException(status_code=500, detail="Failed to create pet due to a database error.")

    async def get_pet(self, db: AsyncSession, pet_id: int, include_deleted: bool = False) -> Optional[models.Pet]:
        """
        Retrieves a pet by its ID.
        Args:
            db (AsyncSession): The database session.
            pet_id (int): The ID of the pet to retrieve.
            include_deleted (bool): If True, also retrieve soft-deleted pets.
        Returns:
            Optional[models.Pet]: The pet ORM object if found, otherwise None.
        """
        query = select(models.Pet).filter(models.Pet.id == pet_id)
        if not include_deleted:
            query = query.filter(models.Pet.is_deleted == False)
        
        result = await db.execute(query)
        pet = result.scalar_one_or_none()
        
        if pet:
            logger.debug(f"Retrieved pet with ID: {pet_id}")
        else:
            logger.debug(f"Pet with ID: {pet_id} not found.")
        return pet

    async def update_pet(self, db: AsyncSession, pet_id: int, pet_data: PetUpdate) -> Optional[models.Pet]:
        """
        Updates an existing pet in the database.
        Args:
            db (AsyncSession): The database session.
            pet_id (int): The ID of the pet to update.
            pet_data (PetUpdate): The data to update (partial updates are supported).
        Returns:
            Optional[models.Pet]: The updated pet ORM object if found, otherwise None.
        """
        # First, check if the pet exists and is not soft-deleted
        existing_pet_query = select(models.Pet).filter(models.Pet.id == pet_id, models.Pet.is_deleted == False)
        result = await db.execute(existing_pet_query)
        db_pet = result.scalar_one_or_none()

        if not db_pet:
            logger.warning(f"Attempted to update non-existent or soft-deleted pet with ID: {pet_id}")
            return None # Pet not found or is soft-deleted

        update_data = pet_data.model_dump(exclude_unset=True, exclude={"id"}) # Exclude 'id' and unset fields

        if not update_data:
            logger.info(f"No fields provided for update for pet ID: {pet_id}. Returning existing pet.")
            return db_pet # No data to update

        # Convert status enum to string if present
        if 'status' in update_data and update_data['status'] is not None:
            update_data['status'] = update_data['status'].value
        
        # Manually update fields as `update().values()` with a dict of optional fields can set None
        # for fields that were not provided in the payload, which is not desired for PATCH-like PUT.
        # So, we iterate over the update_data.
        for key, value in update_data.items():
            # Convert schema names (camelCase) to model names (snake_case)
            if key == 'photoUrls':
                setattr(db_pet, 'photo_urls', value)
            else:
                setattr(db_pet, key, value)

        try:
            db.add(db_pet) # Re-add to session to mark as dirty if needed
            await db.commit()
            await db.refresh(db_pet)
            logger.info(f"Pet with ID: {pet_id} updated successfully.")
            return db_pet
        except Exception as e:
            logger.error(f"Error updating pet with ID: {pet_id}: {e}", exc_info=True)
            await db.rollback()
            raise AppException(status_code=500, detail="Failed to update pet due to a database error.")

    async def delete_pet(self, db: AsyncSession, pet_id: int) -> Optional[models.Pet]:
        """
        Soft deletes a pet by setting its `is_deleted` flag to True.
        Args:
            db (AsyncSession): The database session.
            pet_id (int): The ID of the pet to soft delete.
        Returns:
            Optional[models.Pet]: The soft-deleted pet ORM object if found, otherwise None.
        """
        # First, check if the pet exists and is not already soft-deleted
        existing_pet_query = select(models.Pet).filter(models.Pet.id == pet_id)
        result = await db.execute(existing_pet_query)
        db_pet = result.scalar_one_or_none()

        if not db_pet:
            logger.warning(f"Attempted to soft delete non-existent pet with ID: {pet_id}")
            return None

        if db_pet.is_deleted:
            logger.info(f"Pet with ID: {pet_id} is already soft-deleted.")
            return db_pet # Already deleted, idempotent operation

        db_pet.is_deleted = True
        try:
            db.add(db_pet) # Mark as dirty and prepare for commit
            await db.commit()
            await db.refresh(db_pet)
            logger.info(f"Pet with ID: {pet_id} soft-deleted successfully.")
            return db_pet
        except Exception as e:
            logger.error(f"Error soft-deleting pet with ID: {pet_id}: {e}", exc_info=True)
            await db.rollback()
            raise AppException(status_code=500, detail="Failed to delete pet due to a database error.")