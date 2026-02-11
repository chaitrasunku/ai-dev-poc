import logging
from typing import Dict
from fastapi import APIRouter, Depends, status, HTTPException

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import NotFoundException, ConflictException, AppException
from app.schemas.order import OrderCreate, OrderResponse
from app.services.order import OrderService

router = APIRouter(
    prefix="/store",
    tags=["store"],
    responses={
        400: {"description": "Invalid input"},
        404: {"description": "Order not found / Pet not found"},
        422: {"description": "Validation Error"}
    },
)

logger = logging.getLogger(__name__)

# Instantiate service (can be a dependency if more complex)
order_service = OrderService()

@router.post(
    "/order",
    response_model=OrderResponse,
    status_code=status.HTTP_200_OK, # OpenAPI spec typically returns 200 for successful operations, even for creation.
    summary="Place an order for a pet",
    description="Places a new order for a pet in the store.",
    responses={
        200: {"description": "Order placed successfully"},
        400: {"description": "Invalid Order"},
        404: {"description": "Pet not found"}
    }
)
async def place_order(
    order_data: OrderCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Places a new order.
    """
    logger.info(f"Received request to place order for pet ID: {order_data.petId}, quantity: {order_data.quantity}")
    try:
        new_order = await order_service.place_order(db, order_data)
        return OrderResponse.model_validate(new_order)
    except NotFoundException as e:
        logger.warning(f"Order placement failed: {e.detail}")
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    except AppException as e:
        logger.error(f"AppException during order placement: {e.detail}", exc_info=True)
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    except Exception as e:
        logger.critical(f"Unhandled error during order placement: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An unexpected error occurred.")

@router.get(
    "/inventory",
    response_model=Dict[str, int],
    status_code=status.HTTP_200_OK,
    summary="Returns pet inventories by status",
    description="Returns a map of pet statuses to quantities. Requires authentication for administrative access in a real system, but open for this specification.",
    responses={
        200: {"description": "Successful operation", "content": {"application/json": {"schema": {"type": "object", "additionalProperties": {"type": "integer", "format": "int32"}}}}},
        # 401: {"description": "Unauthorized (if authentication was implemented)"}
    }
)
async def get_inventory(
    db: AsyncSession = Depends(get_db)
):
    """
    Returns pet inventories by status.
    """
    logger.info("Received request to get store inventory.")
    try:
        inventory = await order_service.get_inventory(db)
        return inventory
    except AppException as e:
        logger.error(f"AppException during inventory retrieval: {e.detail}", exc_info=True)
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    except Exception as e:
        logger.critical(f"Unhandled error during inventory retrieval: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An unexpected error occurred.")