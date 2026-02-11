from datetime import datetime
from typing import Optional, List

from sqlalchemy import String, ARRAY, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import ENUM

from petstore.app.database.base import BaseModel
from petstore.app.schemas.common import PetStatus


class Pet(BaseModel):
    """
    SQLAlchemy model for the Pet entity.
    """
    __tablename__ = "pet"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[PetStatus] = mapped_column(
        ENUM(PetStatus, name="pet_status", create_type=False), # create_type=False to avoid recreating enum type on every migration
        default=PetStatus.available,
        nullable=False
    )
    tags: Mapped[List[str]] = mapped_column(ARRAY(String), default=list, nullable=False)
    photo_urls: Mapped[List[str]] = mapped_column(ARRAY(String), default=list, nullable=False)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True) # Soft delete timestamp