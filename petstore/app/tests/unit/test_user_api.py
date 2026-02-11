import pytest
from httpx import AsyncClient
from fastapi import status
from datetime import datetime, timezone, timedelta

from petstore.app.schemas.common import UserStatus


@pytest.mark.asyncio
async def test_create_user_success(client: AsyncClient, override_get_db):
    """Test successful creation of a user."""
    user_data = {
        "username": "newuser",
        "email": "newuser@example.com",
        "password": "strongpassword123",
        "first_name": "New",
        "last_name": "User",
        "phone": "111-222-3333",
        "user_status": UserStatus.active.value
    }
    response = await client.post("/user/", json=user_data)

    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["username"] == "newuser"
    assert data["email"] == "newuser@example.com"
    assert "password" not in data  # Ensure password is not returned
    assert "hashed_password" not in data
    assert data["id"] > 0
    assert "created_at" in data
    assert "updated_at" in data


@pytest.mark.asyncio
async def test_create_user_duplicate_username(client: AsyncClient, override_get_db, test_user_fixture):
    """Test creation of a user with a duplicate username."""
    user_data = {
        "username": test_user_fixture.username,  # Duplicate username
        "email": "another@example.com",
        "password": "anotherpassword"
    }
    response = await client.post("/user/", json=user_data)

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["detail"] == "Username already registered"


@pytest.mark.asyncio
async def test_create_user_duplicate_email(client: AsyncClient, override_get_db, test_user_fixture):
    """Test creation of a user with a duplicate email."""
    user_data = {
        "username": "anotheruser",
        "email": test_user_fixture.email,  # Duplicate email
        "password": "anotherpassword"
    }
    response = await client.post("/user/", json=user_data)

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["detail"] == "Email already registered"


@pytest.mark.asyncio
async def test_create_user_invalid_email(client: AsyncClient, override_get_db):
    """Test creation of a user with an invalid email format."""
    user_data = {
        "username": "invalidemailuser",
        "email": "invalid-email",  # Invalid email format
        "password": "somepassword"
    }
    response = await client.post("/user/", json=user_data)

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert "email" in response.json()["detail"][0]["loc"]


@pytest.mark.asyncio
async def test_create_user_weak_password(client: AsyncClient, override_get_db):
    """Test creation of a user with a password shorter than 6 characters."""
    user_data = {
        "username": "weakpassuser",
        "email": "weak@example.com",
        "password": "weak"  # Too short password
    }
    response = await client.post("/user/", json=user_data)

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert "password" in response.json()["detail"][0]["loc"]


@pytest.mark.asyncio
async def test_login_user_success(client: AsyncClient, override_get_db, test_user_fixture, test_user_data):
    """Test successful user login and token generation."""
    response = await client.get(
        f"/user/login?username={test_user_data['username']}&password={test_user_data['password']}"
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_user_incorrect_password(client: AsyncClient, override_get_db, test_user_fixture, test_user_data):
    """Test login with correct username but incorrect password."""
    response = await client.get(
        f"/user/login?username={test_user_data['username']}&password=wrongpassword"
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json()["detail"] == "Incorrect username or password"


@pytest.mark.asyncio
async def test_login_user_non_existent_username(client: AsyncClient, override_get_db):
    """Test login with a non-existent username."""
    response = await client.get(
        f"/user/login?username=nonexistent&password=anypassword"
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json()["detail"] == "Incorrect username or password"


@pytest.mark.asyncio
async def test_login_user_missing_credentials(client: AsyncClient, override_get_db):
    """Test login with missing username or password query parameters."""
    response = await client.get("/user/login?username=user")  # Missing password
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert "password" in response.json()["detail"][0]["loc"]

    response = await client.get("/user/login?password=pass")  # Missing username
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert "username" in response.json()["detail"][0]["loc"]


@pytest.mark.asyncio
async def test_logout_user_success(client: AsyncClient, override_get_db, auth_headers_fixture: dict):
    """Test successful logout with a valid token."""
    response = await client.get("/user/logout", headers=auth_headers_fixture)

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["message"] == "Successfully logged out (client should discard token)."


@pytest.mark.asyncio
async def test_logout_user_unauthenticated(client: AsyncClient, override_get_db):
    """Test logout without a valid token."""
    response = await client.get("/user/logout")

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json()["detail"] == "Not authenticated"


@pytest.mark.asyncio
async def test_logout_user_invalid_token(client: AsyncClient, override_get_db):
    """Test logout with an invalid JWT token."""
    invalid_headers = {"Authorization": "Bearer invalid_jwt_token"}
    response = await client.get("/user/logout", headers=invalid_headers)

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json()["detail"] == "Could not validate credentials"


@pytest.mark.asyncio
async def test_logout_user_expired_token(client: AsyncClient, override_get_db, test_user_fixture):
    """Test logout with an expired JWT token."""
    # Create an expired token
    expired_token = create_access_token(
        data={"sub": test_user_fixture.username},
        expires_delta=timedelta(minutes=-1) # Expired 1 minute ago
    )
    expired_headers = {"Authorization": f"Bearer {expired_token}"}
    response = await client.get("/user/logout", headers=expired_headers)

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json()["detail"] == "Could not validate credentials"