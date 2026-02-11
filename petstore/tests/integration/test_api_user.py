import pytest
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import models
from app.schemas.user import UserCreate, UserLogin, TokenResponse
from app.core.security import jwt_blocklist

@pytest.mark.asyncio
async def test_create_user_success(client: httpx.AsyncClient, db_session: AsyncSession):
    user_data = UserCreate(
        username="testuser_int",
        firstName="Integration",
        lastName="User",
        email="integration@example.com",
        password="StrongPassword1!",
        phone="111-222-3333",
        userStatus=0
    )
    
    response = await client.post("/user/", json=user_data.model_dump())
    
    assert response.status_code == 201
    response_data = response.json()
    assert response_data["username"] == "testuser_int"
    assert response_data["email"] == "integration@example.com"
    assert "id" in response_data

    # Verify in DB
    db_user = await db_session.get(models.User, response_data["id"])
    assert db_user is not None
    assert db_user.username == "testuser_int"
    assert db_user.email == "integration@example.com"
    assert db_user.first_name == "Integration"
    assert db_user.last_name == "User"
    assert db_user.phone == "111-222-3333"
    assert db_user.user_status == 0
    assert db_user.hashed_password is not None
    assert db_user.hashed_password != user_data.password # Password should be hashed

@pytest.mark.asyncio
async def test_create_user_duplicate_username(client: httpx.AsyncClient, db_session: AsyncSession):
    user_data = UserCreate(username="dupuser", email="dup1@example.com", password="StrongPassword1!")
    await client.post("/user/", json=user_data.model_dump()) # First creation
    
    duplicate_user_data = UserCreate(username="dupuser", email="dup2@example.com", password="StrongPassword2!")
    response = await client.post("/user/", json=duplicate_user_data.model_dump())
    
    assert response.status_code == 409
    assert response.json()["detail"] == "Username 'dupuser' already registered."

@pytest.mark.asyncio
async def test_create_user_duplicate_email(client: httpx.AsyncClient, db_session: AsyncSession):
    user_data = UserCreate(username="user1", email="dup_email@example.com", password="StrongPassword1!")
    await client.post("/user/", json=user_data.model_dump()) # First creation
    
    duplicate_user_data = UserCreate(username="user2", email="dup_email@example.com", password="StrongPassword2!")
    response = await client.post("/user/", json=duplicate_user_data.model_dump())
    
    assert response.status_code == 409
    assert response.json()["detail"] == "Email 'dup_email@example.com' already registered."

@pytest.mark.asyncio
async def test_create_user_invalid_password(client: httpx.AsyncClient):
    invalid_user_data = UserCreate(username="weakpass", email="weak@example.com", password="weak")
    response = await client.post("/user/", json=invalid_user_data.model_dump())
    assert response.status_code == 422 # Pydantic validation error

@pytest.mark.asyncio
async def test_login_user_success(client: httpx.AsyncClient, db_session: AsyncSession):
    user_data = UserCreate(username="loginuser", email="login@example.com", password="LoginPass1!")
    await client.post("/user/", json=user_data.model_dump()) # Create user first
    
    response = await client.get(
        "/user/login",
        params={"username": "loginuser", "password": "LoginPass1!"}
    )
    
    assert response.status_code == 200
    response_data = TokenResponse.model_validate(response.json())
    assert response_data.token is not None

@pytest.mark.asyncio
async def test_login_user_invalid_credentials(client: httpx.AsyncClient):
    # Try logging in with non-existent user
    response = await client.get(
        "/user/login",
        params={"username": "nonexistent", "password": "AnyPassword1!"}
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid username or password."

    # Try logging in with correct user, wrong password
    user_data = UserCreate(username="wrongpassuser", email="wrongpass@example.com", password="CorrectPass1!")
    await client.post("/user/", json=user_data.model_dump())
    response = await client.get(
        "/user/login",
        params={"username": "wrongpassuser", "password": "WrongPass1!"}
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid username or password."

@pytest.mark.asyncio
async def test_login_user_missing_credentials(client: httpx.AsyncClient):
    response = await client.get("/user/login", params={"username": "testuser"}) # Missing password
    assert response.status_code == 400
    assert response.json()["detail"] == "Username and password are required."

    response = await client.get("/user/login", params={"password": "password"}) # Missing username
    assert response.status_code == 400
    assert response.json()["detail"] == "Username and password are required."

@pytest.mark.asyncio
async def test_logout_user_success(client: httpx.AsyncClient, db_session: AsyncSession):
    user_data = UserCreate(username="logoutuser", email="logout@example.com", password="LogoutPass1!")
    await client.post("/user/", json=user_data.model_dump())
    
    login_response = await client.get(
        "/user/login",
        params={"username": "logoutuser", "password": "LogoutPass1!"}
    )
    token = TokenResponse.model_validate(login_response.json()).token

    # Ensure token is not blocked initially
    assert token not in jwt_blocklist

    logout_response = await client.get(
        "/user/logout",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert logout_response.status_code == 200
    assert logout_response.json()["message"] == "Successfully logged out."

    # Verify token is now blocked
    assert token in jwt_blocklist

    # Attempt to use the token for a protected route (e.g., trying to logout again)
    response_after_logout = await client.get(
        "/user/logout",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response_after_logout.status_code == 401
    assert "Token has been revoked." in response_after_logout.json()["detail"]

@pytest.mark.asyncio
async def test_logout_user_no_token(client: httpx.AsyncClient):
    response = await client.get("/user/logout")
    assert response.status_code == 401
    assert "Not authenticated" in response.json()["detail"]

@pytest.mark.asyncio
async def test_logout_user_invalid_token(client: httpx.AsyncClient):
    response = await client.get("/user/logout", headers={"Authorization": "Bearer invalid_token"})
    assert response.status_code == 401
    assert "Could not validate credentials." in response.json()["detail"]