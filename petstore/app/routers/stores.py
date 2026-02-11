import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from petstore.app.database.session import async_get_db
from petstore.app.schemas.order import OrderCreate, OrderResponse
from petstore.app.services.order_service import OrderService
from petstore.app.services.pet_service import PetService
from petstore.app.core.security import async_get_current_user
from petstore.app.models.user import User # Imported for type hinting in current_user

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/order", response_model=OrderResponse, status_code=status.HTTP_201_CREATED, summary="Place a new order")
async def place_order(
    order_data: OrderCreate,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(async_get_current_user) # Protected endpoint
):
    """
    Places a new order for a pet.
    Requires authentication.
    - **pet_id**: ID of the pet to order (must exist and be active)
    - **quantity**: Number of pets to order (default: 1, must be > 0)
    - **ship_date**: Optional ship date
    - **status**: Status of the order (default: placed)
    - **complete**: Whether the order is complete (default: false)
    """
    try:
        new_order = await OrderService.async_place_order(db, order_data)
        return OrderResponse.model_validate(new_order)
    except HTTPException:
        raise # Re-raise HTTPExceptions from service layer (e.g., 404 Pet not found)
    except SQLAlchemyError as e:
        logger.exception(f"Database error while placing order for pet ID {order_data.pet_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Database error occurred.")
    except Exception as e:
        logger.exception(f"An unexpected error occurred while placing order: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error.")


@router.get("/inventory", response_model=dict[str, int], summary="Returns pet inventories by status")
async def get_pet_inventory(
    db: AsyncSession = Depends(async_get_db)
):
    """
    Returns a map of pet statuses to their counts.
    Counts only active (not soft-deleted) pets.
    """
    try:
        inventory = await PetService.async_get_pet_inventory(db)
        return inventory
    except SQLAlchemyError as e:
        logger.exception(f"Database error while retrieving pet inventory: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Database error occurred.")
    except Exception as e:
        logger.exception(f"An unexpected error occurred while retrieving pet inventory: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error.")