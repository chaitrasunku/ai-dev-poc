import logging
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import models
from app.schemas.user import UserCreate, UserLogin
from app.core import security
from app.core.exceptions import ConflictException, UnauthorizedException, AppException

logger = logging.getLogger(__name__)

class UserService:
    """
    Service layer for User operations.
    Encapsulates business logic, including password management and JWT generation.
    """

    async def create_user(self, db: AsyncSession, user_data: UserCreate) -> models.User:
        """
        Creates a new user in the database.
        Checks for existing username or email to prevent conflicts.
        Hashes the password before storing.
        """
        # Check if username already exists
        user_by_username_query = select(models.User).filter(models.User.username == user_data.username)
        user_by_username = (await db.execute(user_by_username_query)).scalar_one_or_none()
        if user_by_username:
            logger.warning(f"Attempted to create user with existing username: {user_data.username}")
            raise ConflictException(detail=f"Username '{user_data.username}' already registered.")

        # Check if email already exists
        user_by_email_query = select(models.User).filter(models.User.email == user_data.email)
        user_by_email = (await db.execute(user_by_email_query)).scalar_one_or_none()
        if user_by_email:
            logger.warning(f"Attempted to create user with existing email: {user_data.email}")
            raise ConflictException(detail=f"Email '{user_data.email}' already registered.")
        
        try:
            hashed_password = security.hash_password(user_data.password)
            db_user = models.User(
                username=user_data.username,
                first_name=user_data.firstName,
                last_name=user_data.lastName,
                email=user_data.email,
                hashed_password=hashed_password,
                phone=user_data.phone,
                user_status=user_data.userStatus,
            )
            db.add(db_user)
            await db.commit()
            await db.refresh(db_user)
            logger.info(f"User created with ID: {db_user.id}, username: {db_user.username}")
            return db_user
        except ConflictException: # Re-raise if caught here
            raise
        except Exception as e:
            logger.error(f"Error creating user {user_data.username}: {e}", exc_info=True)
            await db.rollback()
            raise AppException(status_code=500, detail="Failed to create user due to a database error.")

    async def authenticate_user(self, db: AsyncSession, username: str, password: str) -> Optional[models.User]:
        """
        Authenticates a user by username and password.
        """
        query = select(models.User).filter(models.User.username == username)
        result = await db.execute(query)
        user = result.scalar_one_or_none()

        if not user or not security.verify_password(password, user.hashed_password):
            logger.warning(f"Authentication failed for user: {username}")
            return None
        
        logger.info(f"User {username} authenticated successfully.")
        return user

    async def generate_access_token(self, user: models.User) -> str:
        """
        Generates a JWT access token for the given user.
        """
        access_token = security.create_access_token(
            data={"sub": user.username}
        )
        logger.info(f"Access token generated for user: {user.username}")
        return access_token