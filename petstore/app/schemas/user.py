from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, EmailStr, ConfigDict

from petstore.app.schemas.common import UserStatus


class UserBase(BaseModel):
    """
    Base Pydantic schema for User common fields.
    """
    username: str = Field(min_length=3, max_length=50, description="Unique username for the user")
    first_name: Optional[str] = Field(None, max_length=50, description="User's first name")
    last_name: Optional[str] = Field(None, max_length=50, description="User's last name")
    email: EmailStr = Field(max_length=100, description="Unique email address for the user")
    phone: Optional[str] = Field(None, max_length=20, description="User's phone number")
    user_status: UserStatus = Field(UserStatus.active, description="Current status of the user")


class UserCreate(UserBase):
    """
    Pydantic schema for creating a new User.
    Includes password field for registration.
    """
    password: str = Field(min_length=6, description="Password for the user account")


class UserResponse(UserBase):
    """
    Pydantic schema for responding with User details.
    Excludes sensitive fields like password/hashed_password.
    Includes auto-generated ID and timestamps.
    """
    id: int = Field(gt=0, description="Unique identifier of the user")
    created_at: datetime = Field(description="Timestamp of when the user was created")
    updated_at: datetime = Field(description="Timestamp of the last update")

    model_config = ConfigDict(from_attributes=True)


class Token(BaseModel):
    """
    Pydantic schema for JWT access token response.
    """
    access_token: str = Field(description="JWT access token")
    token_type: str = Field("bearer", description="Type of the token")