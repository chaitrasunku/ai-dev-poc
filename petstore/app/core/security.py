import logging
from datetime import datetime, timedelta, timezone
from typing import Set

from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi.security import OAuth2PasswordBearer
from fastapi import Depends

from app.core.config import settings
from app.core.exceptions import UnauthorizedException
from app.core.database import get_db
from app.database import models
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

logger = logging.getLogger(settings.APP_NAME)

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 bearer token scheme, points to the login endpoint
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="user/login")

# In-memory JWT blocklist for logout functionality
jwt_blocklist: Set[str] = set()

def hash_password(password: str) -> str:
    """Hashes a plain text password."""
    try:
        return pwd_context.hash(password)
    except Exception as e:
        logger.error(f"Error hashing password: {e}", exc_info=True)
        raise UnauthorizedException(detail="Failed to hash password.")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plain text password against a hashed password."""
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict) -> str:
    """
    Creates a JWT access token.
    Args:
        data (dict): The payload data to encode (e.g., {'sub': username}).
    Returns:
        str: The encoded JWT token.
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str) -> dict:
    """
    Decodes and verifies a JWT access token.
    Args:
        token (str): The JWT token string.
    Returns:
        dict: The decoded payload.
    Raises:
        UnauthorizedException: If the token is invalid, expired, or malformed.
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        # Check if token is in blocklist
        if token in jwt_blocklist:
            logger.warning("Attempt to use a blacklisted token.")
            raise UnauthorizedException(detail="Token has been revoked.")
        return payload
    except jwt.ExpiredSignatureError:
        logger.warning("Expired signature in JWT token.")
        raise UnauthorizedException(detail="Token has expired.")
    except JWTError as e:
        logger.warning(f"Invalid JWT token: {e}")
        raise UnauthorizedException(detail="Could not validate credentials.")

def add_to_blocklist(token: str):
    """Adds a JWT token to the in-memory blocklist."""
    jwt_blocklist.add(token)
    logger.info("Token added to blocklist.")

def is_blocked(token: str) -> bool:
    """Checks if a token is in the blocklist."""
    return token in jwt_blocklist

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> models.User:
    """
    FastAPI dependency to get the current authenticated user from a JWT token.
    Raises UnauthorizedException if the token is invalid or the user is not found.
    """
    try:
        payload = decode_access_token(token)
        username: str = payload.get("sub")
        if username is None:
            raise UnauthorizedException()
    except UnauthorizedException:
        raise # Re-raise the UnauthorizedException from decode_access_token or if username is missing

    # Query the database to find the user
    result = await db.execute(select(models.User).filter(models.User.username == username))
    user = result.scalar_one_or_none()

    if user is None:
        logger.warning(f"User '{username}' from token not found in database.")
        raise UnauthorizedException(detail="User not found.")
    
    return user