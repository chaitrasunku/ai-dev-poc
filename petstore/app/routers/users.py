import logging
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError

from petstore.app.database.session import async_get_db
from petstore.app.schemas.user import UserCreate, UserResponse, Token
from petstore.app.services.user_service import UserService
from petstore.app.core.security import authenticate_user, create_access_token, async_get_current_user
from petstore.app.core.config import settings
from petstore.app.core.exceptions import CredentialsException
from petstore.app.models.user import User # Imported for type hinting in current_user

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED, summary="Create user")
async def create_user(
    user_data: UserCreate,
    db: AsyncSession = Depends(async_get_db)
):
    """
    Creates a new user account.
    - **username**: Unique username (min_length=3)
    - **password**: User's password (min_length=6)
    - **email**: Unique and valid email address
    - **first_name**, **last_name**, **phone**: Optional fields
    - **user_status**: User's status (active, inactive, banned, default: active)
    """
    try:
        created_user = await UserService.async_create_user(db, user_data)
        return UserResponse.model_validate(created_user)
    except HTTPException:
        raise # Re-raise HTTPExceptions from service layer (e.g., 400 Bad Request)
    except SQLAlchemyError as e:
        logger.exception(f"Database error while creating user {user_data.username}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Database error occurred.")
    except Exception as e:
        logger.exception(f"An unexpected error occurred while creating user: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error.")


@router.get("/login", response_model=Token, summary="Login user and get JWT token")
async def login_user(
    username: str = Query(..., description="The user name for login"),
    password: str = Query(..., description="The password for login in clear text"),
    db: AsyncSession = Depends(async_get_db)
):
    """
    Authenticates a user with username and password, then generates a JWT token.
    - **username**: User's username (query parameter)
    - **password**: User's password (query parameter)
    """
    user = await authenticate_user(username, password, db)
    if not user:
        raise CredentialsException(detail="Incorrect username or password")

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    logger.info(f"User '{username}' logged in successfully and received JWT token.")
    return Token(access_token=access_token)


@router.get("/logout", summary="Logout user (client-side token discard)")
async def logout_user(
    current_user: User = Depends(async_get_current_user) # Protected endpoint
):
    """
    Logs out the current user. For stateless JWTs, this means
    instructing the client to discard their token. No server-side
    invalidation is performed.
    Requires authentication.
    """
    logger.info(f"User '{current_user.username}' accessed logout endpoint. Client should discard token.")
    return {"message": "Successfully logged out (client should discard token)."}