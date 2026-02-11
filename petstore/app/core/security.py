import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from petstore.app.core.config import settings
from petstore.app.core.exceptions import CredentialsException
from petstore.app.database.session import async_get_db
from petstore.app.models.user import User

logger = logging.getLogger(__name__)

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2PasswordBearer for JWT token extraction from request headers
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="user/login")

def hash_password(password: str) -> str:
    """Hashes a plaintext password using bcrypt."""
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plaintext password against a hashed password."""
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Creates a JWT access token.
    The 'sub' claim should typically be the user's unique identifier (e.g., username).
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc)})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str) -> dict:
    """
    Decodes a JWT access token and returns its payload.
    Raises CredentialsException if the token is invalid or expired.
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError as e:
        logger.warning(f"JWT decoding error: {e}")
        raise CredentialsException(detail="Could not validate credentials") from e

async def authenticate_user(username: str, password: str, db: AsyncSession) -> Optional[User]:
    """
    Authenticates a user by username and password.
    Returns the User object if credentials are valid, otherwise None.
    """
    stmt = select(User).where(User.username == username)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        logger.warning(f"Authentication attempt with non-existent username: {username}")
        return None
    if not verify_password(plain_password=password, hashed_password=user.hashed_password):
        logger.warning(f"Authentication attempt with incorrect password for user: {username}")
        return None
    
    # Also ensure user is active if user_status is being used
    if user.user_status != "active":
        logger.warning(f"Authentication attempt for inactive user: {username}")
        return None

    logger.info(f"User '{username}' authenticated successfully.")
    return user

async def async_get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(async_get_db)
) -> User:
    """
    FastAPI dependency to get the current authenticated user from a JWT token.
    Raises CredentialsException if the token is invalid or user not found/active.
    """
    payload = decode_access_token(token)
    username: str = payload.get("sub")
    if username is None:
        raise CredentialsException(detail="Invalid token payload")

    stmt = select(User).where(User.username == username)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user or user.user_status != "active": # Ensure user exists and is active
        raise CredentialsException(detail="Could not validate credentials")

    logger.debug(f"Current user '{username}' successfully retrieved from token.")
    return user