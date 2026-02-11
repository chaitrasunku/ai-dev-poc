from datetime import datetime
from typing import List, Optional

from sqlalchemy import Column, Integer, String, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import JSONB

from app.core.database import Base

class Pet(Base):
    """
    SQLAlchemy ORM model for pets.
    """
    __tablename__ = "pets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String, nullable=False) # Stores string value of PetStatusEnum
    tags: Mapped[Optional[List[str]]] = mapped_column(JSONB, nullable=True)
    photo_urls: Mapped[Optional[List[str]]] = mapped_column(JSONB, nullable=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    def __repr__(self):
        return f"<Pet(id={self.id}, name='{self.name}', status='{self.status}')>"

class User(Base):
    """
    SQLAlchemy ORM model for users.
    """
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    first_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    last_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String, nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    user_status: Mapped[int] = mapped_column(Integer, default=0, nullable=False) # User Status (e.g., 0=new, 1=active, 2=inactive)

    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}', email='{self.email}')>"

class Order(Base):
    """
    SQLAlchemy ORM model for orders.
    """
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    pet_id: Mapped[int] = mapped_column(Integer, ForeignKey("pets.id"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    ship_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False) # Stores string value of OrderStatusEnum
    complete: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    def __repr__(self):
        return f"<Order(id={self.id}, pet_id='{self.pet_id}', status='{self.status}')>"