from datetime import datetime
from typing import Optional

from sqlalchemy import ForeignKey, Integer, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import ENUM

from petstore.app.database.base import BaseModel
from petstore.app.schemas.common import OrderStatus
from petstore.app.models.pet import Pet


class Order(BaseModel):
    """
    SQLAlchemy model for the Order entity.
    """
    __tablename__ = "order"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    pet_id: Mapped[int] = mapped_column(ForeignKey('pet.id'), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    ship_date: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    status: Mapped[OrderStatus] = mapped_column(
        ENUM(OrderStatus, name="order_status", create_type=False),
        default=OrderStatus.placed,
        nullable=False
    )
    complete: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Define relationship to Pet
    pet: Mapped['Pet'] = relationship('Pet', lazy='joined') # Eager load pet details