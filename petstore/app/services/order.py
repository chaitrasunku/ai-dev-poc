import logging
from typing import Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, case, and_

from app.database import models
from app.schemas.order import OrderCreate, OrderStatusEnum
from app.core.exceptions import NotFoundException, AppException
from app.services.pet import PetService # To check pet existence

logger = logging.getLogger(__name__)

class OrderService:
    """
    Service layer for Order and Store operations.
    Encapsulates business logic for placing orders and retrieving inventory statistics.
    """

    def __init__(self):
        self.pet_service = PetService() # Re-use PetService to check pet existence

    async def place_order(self, db: AsyncSession, order_data: OrderCreate) -> models.Order:
        """
        Places a new order in the database.
        Validates if the pet exists and is not soft-deleted.
        """
        # Validate petId: check if a pet with petId exists and is not soft-deleted
        existing_pet = await self.pet_service.get_pet(db, order_data.petId)
        if not existing_pet:
            logger.warning(f"Attempted to place order for non-existent or soft-deleted pet with ID: {order_data.petId}")
            raise NotFoundException(detail=f"Pet with ID {order_data.petId} not found or is unavailable.")
        
        try:
            db_order = models.Order(
                pet_id=order_data.petId,
                quantity=order_data.quantity,
                ship_date=order_data.shipDate,
                status=order_data.status.value, # Store enum value as string
                complete=order_data.complete
            )
            db.add(db_order)
            await db.commit()
            await db.refresh(db_order)
            logger.info(f"Order placed with ID: {db_order.id} for pet ID: {db_order.pet_id}")
            return db_order
        except NotFoundException: # Re-raise if caught from pet_service
            raise
        except Exception as e:
            logger.error(f"Error placing order for pet ID {order_data.petId}: {e}", exc_info=True)
            await db.rollback()
            raise AppException(status_code=500, detail="Failed to place order due to a database error.")

    async def get_inventory(self, db: AsyncSession) -> Dict[str, int]:
        """
        Retrieves a live summary of pet inventory by status.
        Only counts non-deleted pets.
        """
        result = await db.execute(
            select(
                func.sum(case((models.Pet.status == PetStatusEnum.available.value, 1), else_=0)).label("available"),
                func.sum(case((models.Pet.status == PetStatusEnum.pending.value, 1), else_=0)).label("pending"),
                func.sum(case((models.Pet.status == PetStatusEnum.sold.value, 1), else_=0)).label("sold"),
            ).filter(models.Pet.is_deleted == False) # Only count non-deleted pets
        )
        counts = result.first()

        inventory = {
            "available": counts.available if counts.available is not None else 0,
            "pending": counts.pending if counts.pending is not None else 0,
            "sold": counts.sold if counts.sold is not None else 0,
        }
        logger.info(f"Retrieved pet inventory: {inventory}")
        return inventory