from enum import Enum
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict, PastOrPresentValidator
from typing_extensions import Annotated

class OrderStatusEnum(str, Enum):
    """
    Enum for order statuses.
    """
    placed = "placed"
    approved = "approved"
    delivered = "delivered"

# Pydantic type for shipDate validation
PastOrPresentDatetime = Annotated[datetime, PastOrPresentValidator]

class OrderCreate(BaseModel):
    """
    Schema for placing a new order.
    """
    petId: int = Field(..., description="The ID of the pet being ordered.", ge=1)
    quantity: int = Field(1, description="The quantity of the pet being ordered.", ge=1)
    shipDate: Optional[datetime] = Field(None, description="The date the order is expected to be shipped.", examples=["2024-01-01T12:00:00Z"])
    status: OrderStatusEnum = Field(OrderStatusEnum.placed, description="Current status of the order.")
    complete: bool = Field(False, description="Indicates if the order is complete.")

class OrderResponse(BaseModel):
    """
    Schema for returning order data.
    """
    id: int = Field(..., description="The unique identifier of the order.")
    petId: int = Field(..., description="The ID of the pet associated with the order.")
    quantity: int = Field(..., description="The quantity of the pet ordered.")
    shipDate: Optional[datetime] = Field(None, description="The date the order is expected to be shipped.")
    status: OrderStatusEnum = Field(..., description="Current status of the order.")
    complete: bool = Field(..., description="Indicates if the order is complete.")

    model_config = ConfigDict(from_attributes=True) # Enable ORM mode