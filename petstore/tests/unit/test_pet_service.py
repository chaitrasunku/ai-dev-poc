import pytest
from unittest.mock import AsyncMock, patch
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError

from app.services.pet import PetService
from app.database import models
from app.schemas.pet import PetCreate, PetUpdate, PetStatusEnum
from app.core.exceptions import NotFoundException, ConflictException, AppException

@pytest.fixture
def pet_service():
    return PetService()

@pytest.fixture
def mock_db_session():
    """Mock an AsyncSession object."""
    session = AsyncMock(spec=AsyncSession)
    session.execute.return_value.scalar_one_or_none.return_value = None
    session.commit.return_value = None
    session.refresh.return_value = None
    session.rollback.return_value = None
    return session

@pytest.mark.asyncio
async def test_create_pet_success(pet_service, mock_db_session):
    pet_data = PetCreate(name="Buddy", status=PetStatusEnum.available)
    
    # Configure mock for the scenario where pet is added
    mock_db_session.add.return_value = None
    
    created_pet = await pet_service.create_pet(mock_db_session, pet_data)
    
    assert created_pet.name == pet_data.name
    assert created_pet.status == pet_data.status.value
    assert created_pet.is_deleted is False
    mock_db_session.add.assert_called_once()
    mock_db_session.commit.assert_called_once()
    mock_db_session.refresh.assert_called_once_with(created_pet)

@pytest.mark.asyncio
async def test_create_pet_db_error(pet_service, mock_db_session):
    pet_data = PetCreate(name="Buddy", status=PetStatusEnum.available)
    mock_db_session.commit.side_effect = SQLAlchemyError("DB error")
    
    with pytest.raises(AppException) as exc_info:
        await pet_service.create_pet(mock_db_session, pet_data)
    
    assert exc_info.value.status_code == 500
    assert "Failed to create pet" in exc_info.value.detail
    mock_db_session.rollback.assert_called_once()

@pytest.mark.asyncio
async def test_get_pet_found(pet_service, mock_db_session):
    mock_pet = models.Pet(id=1, name="Buddy", status="available", is_deleted=False)
    mock_db_session.execute.return_value.scalar_one_or_none.return_value = mock_pet
    
    retrieved_pet = await pet_service.get_pet(mock_db_session, 1)
    
    assert retrieved_pet == mock_pet
    mock_db_session.execute.assert_called_once()

@pytest.mark.asyncio
async def test_get_pet_not_found(pet_service, mock_db_session):
    mock_db_session.execute.return_value.scalar_one_or_none.return_value = None
    
    retrieved_pet = await pet_service.get_pet(mock_db_session, 999)
    
    assert retrieved_pet is None
    mock_db_session.execute.assert_called_once()

@pytest.mark.asyncio
async def test_get_pet_deleted_filtered_out(pet_service, mock_db_session):
    mock_pet = models.Pet(id=1, name="Buddy", status="available", is_deleted=True)
    mock_db_session.execute.return_value.scalar_one_or_none.return_value = mock_pet # Simulate initial find
    
    retrieved_pet = await pet_service.get_pet(mock_db_session, 1) # Should filter out is_deleted=True
    
    assert retrieved_pet is None # Because get_pet filters for is_deleted=False by default

@pytest.mark.asyncio
async def test_get_pet_deleted_included(pet_service, mock_db_session):
    mock_pet = models.Pet(id=1, name="Buddy", status="available", is_deleted=True)
    mock_db_session.execute.return_value.scalar_one_or_none.return_value = mock_pet
    
    retrieved_pet = await pet_service.get_pet(mock_db_session, 1, include_deleted=True)
    
    assert retrieved_pet == mock_pet

@pytest.mark.asyncio
async def test_update_pet_success_partial(pet_service, mock_db_session):
    mock_pet = models.Pet(id=1, name="Old Name", status="available", tags=["old"], is_deleted=False)
    mock_db_session.execute.return_value.scalar_one_or_none.return_value = mock_pet
    
    update_data = PetUpdate(id=1, name="New Name", tags=["new"])
    
    updated_pet = await pet_service.update_pet(mock_db_session, 1, update_data)
    
    assert updated_pet.name == "New Name"
    assert updated_pet.status == "available" # Status should remain unchanged
    assert updated_pet.tags == ["new"]
    mock_db_session.commit.assert_called_once()
    mock_db_session.refresh.assert_called_once_with(mock_pet)

@pytest.mark.asyncio
async def test_update_pet_not_found(pet_service, mock_db_session):
    mock_db_session.execute.return_value.scalar_one_or_none.return_value = None # Pet not found
    update_data = PetUpdate(id=999, name="New Name")
    
    updated_pet = await pet_service.update_pet(mock_db_session, 999, update_data)
    
    assert updated_pet is None
    mock_db_session.commit.assert_not_called()

@pytest.mark.asyncio
async def test_update_pet_db_error(pet_service, mock_db_session):
    mock_pet = models.Pet(id=1, name="Old Name", status="available", is_deleted=False)
    mock_db_session.execute.return_value.scalar_one_or_none.return_value = mock_pet
    mock_db_session.commit.side_effect = SQLAlchemyError("DB error")
    
    update_data = PetUpdate(id=1, name="New Name")
    
    with pytest.raises(AppException) as exc_info:
        await pet_service.update_pet(mock_db_session, 1, update_data)
    
    assert exc_info.value.status_code == 500
    assert "Failed to update pet" in exc_info.value.detail
    mock_db_session.rollback.assert_called_once()

@pytest.mark.asyncio
async def test_delete_pet_success(pet_service, mock_db_session):
    mock_pet = models.Pet(id=1, name="Buddy", status="available", is_deleted=False)
    mock_db_session.execute.return_value.scalar_one_or_none.return_value = mock_pet
    
    deleted_pet = await pet_service.delete_pet(mock_db_session, 1)
    
    assert deleted_pet.id == 1
    assert deleted_pet.is_deleted is True
    mock_db_session.commit.assert_called_once()
    mock_db_session.refresh.assert_called_once_with(mock_pet)

@pytest.mark.asyncio
async def test_delete_pet_not_found(pet_service, mock_db_session):
    mock_db_session.execute.return_value.scalar_one_or_none.return_value = None # Pet not found
    
    deleted_pet = await pet_service.delete_pet(mock_db_session, 999)
    
    assert deleted_pet is None
    mock_db_session.commit.assert_not_called()

@pytest.mark.asyncio
async def test_delete_pet_already_deleted(pet_service, mock_db_session):
    mock_pet = models.Pet(id=1, name="Buddy", status="available", is_deleted=True)
    mock_db_session.execute.return_value.scalar_one_or_none.return_value = mock_pet
    
    deleted_pet = await pet_service.delete_pet(mock_db_session, 1)
    
    assert deleted_pet == mock_pet
    assert deleted_pet.is_deleted is True
    mock_db_session.commit.assert_not_called() # Should not commit if already deleted

@pytest.mark.asyncio
async def test_delete_pet_db_error(pet_service, mock_db_session):
    mock_pet = models.Pet(id=1, name="Buddy", status="available", is_deleted=False)
    mock_db_session.execute.return_value.scalar_one_or_none.return_value = mock_pet
    mock_db_session.commit.side_effect = SQLAlchemyError("DB error")
    
    with pytest.raises(AppException) as exc_info:
        await pet_service.delete_pet(mock_db_session, 1)
    
    assert exc_info.value.status_code == 500
    assert "Failed to delete pet" in exc_info.value.detail
    mock_db_session.rollback.assert_called_once()

@pytest.mark.asyncio
async def test_update_pet_no_fields_provided(pet_service, mock_db_session):
    mock_pet = models.Pet(id=1, name="Old Name", status="available", is_deleted=False)
    mock_db_session.execute.return_value.scalar_one_or_none.return_value = mock_pet
    
    update_data = PetUpdate(id=1) # No fields to update
    
    updated_pet = await pet_service.update_pet(mock_db_session, 1, update_data)
    
    assert updated_pet == mock_pet # Should return the original pet
    mock_db_session.commit.assert_not_called()
    mock_db_session.refresh.assert_not_called() # No refresh if no update