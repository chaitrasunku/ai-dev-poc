import logging
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from petstore.app.models.order import Order
from petstore.app.schemas.order import OrderCreate
from petstore.app.services.pet_service import PetService # Import PetService to check for pet existence

logger = logging.getLogger(__name__)


class OrderService:
    """
    Service layer for Order-related business logic and database operations.
    """

    @staticmethod
    async def async_place_order(db: AsyncSession, order_data: OrderCreate) -> Order:
        """
        Places a new order in the database.
        Validates that the pet exists and is not soft-deleted.
        """
        # Verify that the pet_id refers to an existing, active pet
        pet = await PetService.async_get_pet_by_id(db, order_data.pet_id)
        if not pet:
            logger.warning(f"Attempted to place order for non-existent or soft-deleted pet ID: {order_data.pet_id}")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pet not found")

        # Pydantic `Field(gt=0)` handles quantity validation
        new_order = Order(
            pet_id=order_data.pet_id,
            quantity=order_data.quantity,
            ship_date=order_data.ship_date,
            status=order_data.status,
            complete=order_data.complete
        )
        db.add(new_order)
        await db.commit()
        await db.refresh(new_order)
        logger.info(f"Order placed with ID: {new_order.id} for pet ID: {new_order.pet_id}")
        return new_order