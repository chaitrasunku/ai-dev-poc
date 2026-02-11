from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict

from petstore.app.schemas.common import OrderStatus


class OrderBase(BaseModel):
    """
    Base Pydantic schema for Order common fields.
    """
    pet_id: int = Field(gt=0, description="ID of the pet being ordered")
    quantity: int = Field(gt=0, default=1, description="Number of pets ordered")
    ship_date: Optional[datetime] = Field(None, description="Date when the order is expected to be shipped")
    status: OrderStatus = Field(OrderStatus.placed, description="Status of the order")
    complete: bool = Field(False, description="Whether the order has been completed")


class OrderCreate(OrderBase):
    """
    Pydantic schema for creating a new Order.
    Inherits common fields from OrderBase.
    """
    pass


class OrderResponse(OrderBase):
    """
    Pydantic schema for responding with Order details.
    Includes auto-generated ID and timestamps.
    """
    id: int = Field(gt=0, description="Unique identifier of the order")
    created_at: datetime = Field(description="Timestamp of when the order was placed")
    updated_at: datetime = Field(description="Timestamp of the last update")

    model_config = ConfigDict(from_attributes=True)