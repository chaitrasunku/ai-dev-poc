import logging
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import select, or_
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from petstore.app.models.user import User
from petstore.app.schemas.user import UserCreate
from petstore.app.core.security import hash_password

logger = logging.getLogger(__name__)


class UserService:
    """
    Service layer for User-related business logic and database operations.
    """

    @staticmethod
    async def async_create_user(db: AsyncSession, user_data: UserCreate) -> User:
        """
        Creates a new user in the database, hashing the password.
        Checks for unique username and email before creation.
        """
        # Check for existing username or email
        existing_user_stmt = select(User).where(
            or_(User.username == user_data.username, User.email == user_data.email)
        )
        existing_user = await db.execute(existing_user_stmt)
        if existing_user.scalar_one_or_none():
            if (await db.execute(select(User).where(User.username == user_data.username))).scalar_one_or_none():
                logger.warning(f"Attempted to create user with duplicate username: {user_data.username}")
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already registered")
            if (await db.execute(select(User).where(User.email == user_data.email))).scalar_one_or_none():
                logger.warning(f"Attempted to create user with duplicate email: {user_data.email}")
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

        # Hash the password
        hashed_password = hash_password(user_data.password)

        new_user = User(
            username=user_data.username,
            first_name=user_data.first_name,
            last_name=user_data.last_name,
            email=user_data.email,
            hashed_password=hashed_password,
            phone=user_data.phone,
            user_status=user_data.user_status
        )
        db.add(new_user)
        try:
            await db.commit()
            await db.refresh(new_user)
            logger.info(f"User created with ID: {new_user.id} and username: {new_user.username}")
            return new_user
        except SQLAlchemyError as e:
            await db.rollback()
            logger.exception(f"Database error while creating user {user_data.username}: {e}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Database error occurred.")

    @staticmethod
    async def async_get_user_by_username(db: AsyncSession, username: str) -> Optional[User]:
        """
        Retrieves a user by their username.
        """
        stmt = select(User).where(User.username == username)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()