from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict, EmailStr, BeforeValidator
from typing_extensions import Annotated


# Custom type for non-empty string validation
NonEmptyString = Annotated[str, BeforeValidator(lambda v: v if v and v.strip() else None)]

class PetStatusEnum(str, Enum):
    """
    Enum for pet statuses.
    """
    available = "available"
    pending = "pending"
    sold = "sold"

class PetCreate(BaseModel):
    """
    Schema for creating a new pet.
    """
    name: NonEmptyString = Field(..., description="The name of the pet.")
    status: PetStatusEnum = Field(PetStatusEnum.available, description="Current status of the pet.")
    tags: List[str] = Field(default_factory=list, description="A list of tags for the pet.")
    photoUrls: List[str] = Field(default_factory=list, description="A list of photo URLs for the pet.")

    # Pydantic validation to ensure name is not empty
    # @field_validator("name")
    # @classmethod
    # def name_not_empty(cls, v: str) -> str:
    #     if not v or not v.strip():
    #         raise ValueError("Name cannot be empty.")
    #     return v

class PetUpdate(BaseModel):
    """
    Schema for updating an existing pet. All fields are optional.
    For PUT /pet, the ID is required in the body.
    """
    id: int = Field(..., description="The ID of the pet to update.", ge=1)
    name: Optional[NonEmptyString] = Field(None, description="The name of the pet.")
    status: Optional[PetStatusEnum] = Field(None, description="Current status of the pet.")
    tags: Optional[List[str]] = Field(None, description="A list of tags for the pet.")
    photoUrls: Optional[List[str]] = Field(None, description="A list of photo URLs for the pet.")

class PetResponse(BaseModel):
    """
    Schema for returning pet data.
    """
    id: int = Field(..., description="The unique identifier of the pet.")
    name: str = Field(..., description="The name of the pet.")
    status: PetStatusEnum = Field(..., description="Current status of the pet.")
    tags: List[str] = Field(default_factory=list, description="A list of tags for the pet.")
    photoUrls: List[str] = Field(default_factory=list, description="A list of photo URLs for the pet.")
    is_deleted: bool = Field(False, description="Indicates if the pet has been soft-deleted.")

    model_config = ConfigDict(from_attributes=True) # Enable ORM mode