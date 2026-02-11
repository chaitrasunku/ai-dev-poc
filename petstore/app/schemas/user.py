from typing import Optional
from pydantic import BaseModel, Field, EmailStr, ConfigDict, validator
import re

class UserCreate(BaseModel):
    """
    Schema for creating a new user. Includes password complexity validation.
    """
    username: str = Field(..., min_length=3, max_length=50, description="Unique username.")
    firstName: Optional[str] = Field(None, max_length=50, description="User's first name.")
    lastName: Optional[str] = Field(None, max_length=50, description="User's last name.")
    email: EmailStr = Field(..., description="User's email address.")
    password: str = Field(..., min_length=8, description="User's password.")
    phone: Optional[str] = Field(None, max_length=20, description="User's phone number.")
    userStatus: int = Field(0, description="User Status (e.g., 0=new, 1=active).")

    @validator('password')
    def password_strength(cls, v):
        """
        Validates password strength: minimum 8 characters,
        at least one uppercase, one lowercase, one digit, one special character.
        """
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long.")
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter.")
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain at least one lowercase letter.")
        if not re.search(r"[0-9]", v):
            raise ValueError("Password must contain at least one digit.")
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", v):
            raise ValueError("Password must contain at least one special character.")
        return v

class UserLogin(BaseModel):
    """
    Schema for user login credentials.
    """
    username: str = Field(..., min_length=1, description="Username for login.")
    password: str = Field(..., min_length=1, description="Password for login.")

class UserResponse(BaseModel):
    """
    Schema for returning user data.
    """
    id: int = Field(..., description="The unique identifier of the user.")
    username: str = Field(..., description="Unique username.")
    firstName: Optional[str] = Field(None, description="User's first name.")
    lastName: Optional[str] = Field(None, description="User's last name.")
    email: EmailStr = Field(..., description="User's email address.")
    phone: Optional[str] = Field(None, description="User's phone number.")
    userStatus: int = Field(..., description="User Status.")

    model_config = ConfigDict(from_attributes=True) # Enable ORM mode

class TokenResponse(BaseModel):
    """
    Schema for returning an access token after successful login.
    """
    token: str = Field(..., description="JWT access token.")