from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, Field, ConfigDict

from petstore.app.schemas.common import PetStatus


class PetBase(BaseModel):
    """
    Base Pydantic schema for Pet common fields.
    """
    name: str = Field(min_length=1, description="Name of the pet")
    status: PetStatus = Field(PetStatus.available, description="Status of the pet")
    tags: Optional[List[str]] = Field(None, description="List of tags associated with the pet")
    photo_urls: Optional[List[str]] = Field(None, description="List of photo URLs for the pet")


class PetCreate(PetBase):
    """
    Pydantic schema for creating a new Pet.
    Inherits common fields from PetBase.
    """
    # No additional fields needed for creation, ID is auto-generated
    pass


class PetReplace(PetBase):
    """
    Pydantic schema for replacing an existing Pet (PUT operation).
    Includes ID and last_updated_at for optimistic locking.
    All fields are expected to be provided for a full replacement.
    """
    id: int = Field(gt=0, description="Unique identifier of the pet")
    last_updated_at: datetime = Field(description="Timestamp of the last update for optimistic locking")


class PetResponse(PetBase):
    """
    Pydantic schema for responding with Pet details.
    Includes auto-generated ID and timestamps.
    """
    id: int = Field(gt=0, description="Unique identifier of the pet")
    created_at: datetime = Field(description="Timestamp of when the pet was created")
    updated_at: datetime = Field(description="Timestamp of the last update")

    model_config = ConfigDict(from_attributes=True)