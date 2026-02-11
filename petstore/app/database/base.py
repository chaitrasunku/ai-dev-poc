from datetime import datetime
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import declarative_base, Mapped, mapped_column

# Base class for SQLAlchemy declarative models
Base = declarative_base()

class BaseModel(Base):
    """
    Base model providing common fields like created_at and updated_at.
    """
    __abstract__ = True  # This tells SQLAlchemy not to create a table for BaseModel

    # Automatically set creation timestamp
    created_at: Mapped[datetime] = mapped_column(
        default=func.now(),
        nullable=False
    )
    # Automatically update timestamp on modification
    updated_at: Mapped[datetime] = mapped_column(
        default=func.now(),
        onupdate=func.now(),
        nullable=False
    )