import pytest
from unittest.mock import AsyncMock, patch
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError
from app.services.user import UserService
from app.database import models
from app.schemas.user import UserCreate, UserLogin
from app.core.exceptions import ConflictException, UnauthorizedException, AppException
from app.core import security

@pytest.fixture
def user_service():
    return UserService()

@pytest.fixture
def mock_db_session():
    """Mock an AsyncSession object."""
    session = AsyncMock(spec=AsyncSession)
    session.execute.return_value.scalar_one_or_none.return_value = None
    session.commit.return_value = None
    session.refresh.return_value = None
    session.rollback.return_value = None
    return session

# Mock security functions globally for unit tests
@pytest.fixture(autouse=True)
def mock_security():
    with patch('app.core.security.hash_password') as mock_hash_password, \
         patch('app.core.security.verify_password') as mock_verify_password, \
         patch('app.core.security.create_access_token') as mock_create_access_token:
        
        mock_hash_password.return_value = "hashed_password"
        mock_verify_password.return_value = True
        mock_create_access_token.return_value = "mock_jwt_token"
        yield

@pytest.mark.asyncio
async def test_create_user_success(user_service, mock_db_session):
    user_data = UserCreate(
        username="testuser",
        email="test@example.com",
        password="StrongPassword1!",
        firstName="Test",
        lastName="User"
    )
    
    created_user = await user_service.create_user(mock_db_session, user_data)
    
    assert created_user.username == user_data.username
    assert created_user.email == user_data.email
    assert created_user.hashed_password == "hashed_password"
    mock_db_session.add.assert_called_once()
    mock_db_session.commit.assert_called_once()
    mock_db_session.refresh.assert_called_once_with(created_user)

@pytest.mark.asyncio
async def test_create_user_duplicate_username(user_service, mock_db_session):
    user_data = UserCreate(username="existinguser", email="new@example.com", password="StrongPassword1!")
    
    # Simulate username already existing
    mock_db_session.execute.return_value.scalar_one_or_none.side_effect = [
        models.User(username="existinguser"), # First call for username check
        None # Second call for email check
    ]
    
    with pytest.raises(ConflictException) as exc_info:
        await user_service.create_user(mock_db_session, user_data)
    
    assert "Username 'existinguser' already registered." in exc_info.value.detail
    mock_db_session.commit.assert_not_called()

@pytest.mark.asyncio
async def test_create_user_duplicate_email(user_service, mock_db_session):
    user_data = UserCreate(username="newuser", email="existing@example.com", password="StrongPassword1!")
    
    # Simulate email already existing
    mock_db_session.execute.return_value.scalar_one_or_none.side_effect = [
        None, # First call for username check
        models.User(email="existing@example.com") # Second call for email check
    ]
    
    with pytest.raises(ConflictException) as exc_info:
        await user_service.create_user(mock_db_session, user_data)
    
    assert "Email 'existing@example.com' already registered." in exc_info.value.detail
    mock_db_session.commit.assert_not_called()

@pytest.mark.asyncio
async def test_create_user_db_error(user_service, mock_db_session):
    user_data = UserCreate(username="testuser", email="test@example.com", password="StrongPassword1!")
    mock_db_session.commit.side_effect = SQLAlchemyError("DB error")
    
    with pytest.raises(AppException) as exc_info:
        await user_service.create_user(mock_db_session, user_data)
    
    assert exc_info.value.status_code == 500
    assert "Failed to create user" in exc_info.value.detail
    mock_db_session.rollback.assert_called_once()

@pytest.mark.asyncio
async def test_authenticate_user_success(user_service, mock_db_session):
    mock_user = models.User(username="testuser", hashed_password="hashed_password")
    mock_db_session.execute.return_value.scalar_one_or_none.return_value = mock_user
    security.verify_password.return_value = True
    
    authenticated_user = await user_service.authenticate_user(mock_db_session, "testuser", "password")
    
    assert authenticated_user == mock_user
    security.verify_password.assert_called_once_with("password", "hashed_password")

@pytest.mark.asyncio
async def test_authenticate_user_not_found(user_service, mock_db_session):
    mock_db_session.execute.return_value.scalar_one_or_none.return_value = None
    
    authenticated_user = await user_service.authenticate_user(mock_db_session, "nonexistent", "password")
    
    assert authenticated_user is None
    security.verify_password.assert_not_called()

@pytest.mark.asyncio
async def test_authenticate_user_invalid_password(user_service, mock_db_session):
    mock_user = models.User(username="testuser", hashed_password="hashed_password")
    mock_db_session.execute.return_value.scalar_one_or_none.return_value = mock_user
    security.verify_password.return_value = False # Simulate incorrect password
    
    authenticated_user = await user_service.authenticate_user(mock_db_session, "testuser", "wrongpassword")
    
    assert authenticated_user is None
    security.verify_password.assert_called_once_with("wrongpassword", "hashed_password")

@pytest.mark.asyncio
async def test_generate_access_token_success(user_service, mock_db_session):
    mock_user = models.User(username="testuser")
    
    token = await user_service.generate_access_token(mock_user)
    
    assert token == "mock_jwt_token"
    security.create_access_token.assert_called_once_with(data={"sub": "testuser"})