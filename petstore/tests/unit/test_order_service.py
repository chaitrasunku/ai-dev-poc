import pytest
from unittest.mock import AsyncMock, patch
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError
from app.services.order import OrderService
from app.services.pet import PetService
from app.database import models
from app.schemas.order import OrderCreate, OrderStatusEnum
from app.schemas.pet import PetStatusEnum
from app.core.exceptions import NotFoundException, AppException

@pytest.fixture
def order_service():
    return OrderService()

@pytest.fixture
def mock_db_session():
    """Mock an AsyncSession object."""
    session = AsyncMock(spec=AsyncSession)
    session.execute.return_value.scalar_one_or_none.return_value = None
    session.commit.return_value = None
    session.refresh.return_value = None
    session.rollback.return_value = None
    # For inventory, mock execute to return a result object with a first() method
    session.execute.return_value.first.return_value = AsyncMock(available=0, pending=0, sold=0)
    return session

@pytest.fixture
def mock_pet_service():
    """Mock PetService to control pet existence checks."""
    service = AsyncMock(spec=PetService)
    service.get_pet.return_value = None # Default: no pet found
    return service

@pytest.mark.asyncio
async def test_place_order_success(order_service, mock_db_session, mock_pet_service):
    # Setup: Pet exists and is available
    mock_pet_service.get_pet.return_value = models.Pet(id=1, name="Buddy", status=PetStatusEnum.available.value, is_deleted=False)
    order_service.pet_service = mock_pet_service # Inject mock
    
    order_data = OrderCreate(petId=1, quantity=1, status=OrderStatusEnum.placed)
    
    created_order = await order_service.place_order(mock_db_session, order_data)
    
    assert created_order.pet_id == order_data.petId
    assert created_order.quantity == order_data.quantity
    assert created_order.status == order_data.status.value
    mock_pet_service.get_pet.assert_called_once_with(mock_db_session, 1)
    mock_db_session.add.assert_called_once()
    mock_db_session.commit.assert_called_once()
    mock_db_session.refresh.assert_called_once_with(created_order)

@pytest.mark.asyncio
async def test_place_order_pet_not_found(order_service, mock_db_session, mock_pet_service):
    # Setup: PetService indicates pet not found
    mock_pet_service.get_pet.return_value = None
    order_service.pet_service = mock_pet_service # Inject mock
    
    order_data = OrderCreate(petId=999, quantity=1, status=OrderStatusEnum.placed)
    
    with pytest.raises(NotFoundException) as exc_info:
        await order_service.place_order(mock_db_session, order_data)
    
    assert "Pet with ID 999 not found or is unavailable." in exc_info.value.detail
    mock_pet_service.get_pet.assert_called_once_with(mock_db_session, 999)
    mock_db_session.add.assert_not_called()
    mock_db_session.commit.assert_not_called()

@pytest.mark.asyncio
async def test_place_order_db_error(order_service, mock_db_session, mock_pet_service):
    # Setup: Pet exists, but DB operation fails
    mock_pet_service.get_pet.return_value = models.Pet(id=1, name="Buddy", status=PetStatusEnum.available.value, is_deleted=False)
    order_service.pet_service = mock_pet_service # Inject mock
    mock_db_session.commit.side_effect = SQLAlchemyError("DB error")
    
    order_data = OrderCreate(petId=1, quantity=1, status=OrderStatusEnum.placed)
    
    with pytest.raises(AppException) as exc_info:
        await order_service.place_order(mock_db_session, order_data)
    
    assert exc_info.value.status_code == 500
    assert "Failed to place order" in exc_info.value.detail
    mock_db_session.rollback.assert_called_once()

@pytest.mark.asyncio
async def test_get_inventory_empty(order_service, mock_db_session):
    # Setup: mock_db_session's first() returns all zeros by default
    inventory = await order_service.get_inventory(mock_db_session)
    
    assert inventory == {"available": 0, "pending": 0, "sold": 0}
    mock_db_session.execute.assert_called_once()

@pytest.mark.asyncio
async def test_get_inventory_with_data(order_service, mock_db_session):
    # Simulate counts from the database
    mock_db_session.execute.return_value.first.return_value = AsyncMock(available=5, pending=2, sold=3)
    
    inventory = await order_service.get_inventory(mock_db_session)
    
    assert inventory == {"available": 5, "pending": 2, "sold": 3}
    mock_db_session.execute.assert_called_once()

@pytest.mark.asyncio
async def test_get_inventory_db_error(order_service, mock_db_session):
    mock_db_session.execute.side_effect = SQLAlchemyError("DB error")
    
    with pytest.raises(AppException) as exc_info:
        await order_service.get_inventory(mock_db_session)
    
    assert exc_info.value.status_code == 500
    assert "Failed to retrieve inventory" in exc_info.value.detail # This message is generic from router, service raises base exception
    mock_db_session.execute.assert_called_once()