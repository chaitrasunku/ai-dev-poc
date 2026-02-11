import logging
from typing import List
from fastapi import APIRouter, Depends, status, HTTPException, Query, Security

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import NotFoundException, ConflictException, UnauthorizedException, AppException
from app.schemas.user import UserCreate, UserLogin, UserResponse, TokenResponse
from app.services.user import UserService
from app.core.security import get_current_user, oauth2_scheme, add_to_blocklist

router = APIRouter(
    prefix="/user",
    tags=["user"],
    responses={
        400: {"description": "Invalid input"},
        401: {"description": "Unauthorized"},
        403: {"description": "Forbidden"},
        404: {"description": "User not found"},
        409: {"description": "Conflict"},
        422: {"description": "Validation Error"}
    },
)

logger = logging.getLogger(__name__)

# Instantiate service (can be a dependency if more complex)
user_service = UserService()

@router.post(
    "/",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create user",
    description="Creates a new user in the system.",
    responses={
        201: {"description": "User created successfully"},
        409: {"description": "User already exists with that username or email"},
        422: {"description": "Validation error"}
    }
)
async def create_user(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Creates a new user.
    """
    logger.info(f"Received request to create user: {user_data.username}")
    try:
        new_user = await user_service.create_user(db, user_data)
        return UserResponse.model_validate(new_user)
    except ConflictException as e:
        logger.warning(f"User creation failed due to conflict: {e.detail}")
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    except AppException as e:
        logger.error(f"AppException during user creation: {e.detail}", exc_info=True)
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    except Exception as e:
        logger.critical(f"Unhandled error during user creation: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An unexpected error occurred.")

@router.get(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Logs user into the system",
    description="Authenticates user credentials and returns an access token.",
    responses={
        200: {"description": "Successful operation", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/TokenResponse"}}}},
        400: {"description": "Invalid username/password supplied"},
        401: {"description": "Authentication failed"}
    }
)
async def login_user(
    username: str = Query(..., description="The user name for login"),
    password: str = Query(..., description="The password for login in clear text"),
    db: AsyncSession = Depends(get_db)
):
    """
    Logs user into the system.
    """
    logger.info(f"Received login request for user: {username}")
    if not username or not password:
        logger.warning("Login attempt with missing username or password.")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username and password are required.")

    user = await user_service.authenticate_user(db, username, password)
    if not user:
        logger.warning(f"Login failed for user: {username}")
        raise UnauthorizedException(detail="Invalid username or password.")
    
    token = await user_service.generate_access_token(user)
    return TokenResponse(token=token)

@router.get(
    "/logout",
    status_code=status.HTTP_200_OK,
    summary="Logs out current logged in user session",
    description="Invalidates the current user's access token.",
    responses={
        200: {"description": "Successfully logged out"},
        401: {"description": "Unauthorized - No valid token provided or token is expired/invalid"}
    }
)
async def logout_user(
    current_user: UserResponse = Security(get_current_user), # Use Security for OpenAPI docs and to get user
    token: str = Depends(oauth2_scheme) # Directly get the token from the header for blocklisting
):
    """
    Logs out current logged in user session by invalidating their token.
    """
    logger.info(f"User {current_user.username} requested logout.")
    add_to_blocklist(token)
    return {"message": "Successfully logged out."}