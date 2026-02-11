import pytest
from httpx import AsyncClient
from fastapi import status
from datetime import datetime, timezone, timedelta

from petstore.app.schemas.common import PetStatus


@pytest.mark.asyncio
async def test_add_pet_success(client: AsyncClient, override_get_db, auth_headers_fixture: dict):
    """Test successful creation of a pet."""
    pet_data = {
        "name": "Buddy",
        "status": "available",
        "tags": ["dog", "golden"],
        "photo_urls": ["http://example.com/buddy.jpg"]
    }
    response = await client.post("/pet/", json=pet_data, headers=auth_headers_fixture)

    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["name"] == "Buddy"
    assert data["status"] == "available"
    assert data["id"] > 0
    assert "created_at" in data
    assert "updated_at" in data


@pytest.mark.asyncio
async def test_add_pet_invalid_input(client: AsyncClient, override_get_db, auth_headers_fixture: dict):
    """Test creation of a pet with invalid input (missing name)."""
    pet_data = {
        "status": "available",
        "tags": ["dog"],
        "photo_urls": []
    }
    response = await client.post("/pet/", json=pet_data, headers=auth_headers_fixture)

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert "name" in response.json()["detail"][0]["loc"]


@pytest.mark.asyncio
async def test_add_pet_invalid_status(client: AsyncClient, override_get_db, auth_headers_fixture: dict):
    """Test creation of a pet with invalid status enum."""
    pet_data = {
        "name": "Buddy",
        "status": "invalid_status",
        "tags": ["dog"],
        "photo_urls": []
    }
    response = await client.post("/pet/", json=pet_data, headers=auth_headers_fixture)

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert "status" in response.json()["detail"][0]["loc"]


@pytest.mark.asyncio
async def test_add_pet_unauthenticated(client: AsyncClient, override_get_db):
    """Test creation of a pet without authentication."""
    pet_data = {
        "name": "Buddy",
        "status": "available",
    }
    response = await client.post("/pet/", json=pet_data)

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert "detail" in response.json()


@pytest.mark.asyncio
async def test_get_pet_by_id_success(client: AsyncClient, override_get_db, auth_headers_fixture: dict):
    """Test retrieving an existing pet by ID."""
    # First, create a pet
    pet_data = {"name": "TestPet", "status": "available"}
    create_response = await client.post("/pet/", json=pet_data, headers=auth_headers_fixture)
    pet_id = create_response.json()["id"]

    response = await client.get(f"/pet/{pet_id}")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["id"] == pet_id
    assert data["name"] == "TestPet"


@pytest.mark.asyncio
async def test_get_pet_by_id_not_found(client: AsyncClient, override_get_db):
    """Test retrieving a non-existent pet."""
    response = await client.get("/pet/9999")
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json()["detail"] == "Pet not found"


@pytest.mark.asyncio
async def test_get_pet_by_id_soft_deleted(client: AsyncClient, override_get_db, auth_headers_fixture: dict):
    """Test retrieving a soft-deleted pet should return 404."""
    # Create pet
    pet_data = {"name": "DeletedPet", "status": "available"}
    create_response = await client.post("/pet/", json=pet_data, headers=auth_headers_fixture)
    pet_id = create_response.json()["id"]

    # Delete pet
    await client.delete(f"/pet/{pet_id}", headers=auth_headers_fixture)

    # Attempt to retrieve
    response = await client.get(f"/pet/{pet_id}")
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json()["detail"] == "Pet not found"


@pytest.mark.asyncio
async def test_update_pet_success(client: AsyncClient, override_get_db, auth_headers_fixture: dict):
    """Test successful update of a pet with optimistic locking."""
    # Create a pet
    pet_data = {"name": "OldName", "status": PetStatus.available.value, "tags": [], "photo_urls": []}
    create_response = await client.post("/pet/", json=pet_data, headers=auth_headers_fixture)
    created_pet = create_response.json()
    pet_id = created_pet["id"]
    last_updated_at = created_pet["updated_at"]

    # Update the pet
    updated_pet_data = {
        "id": pet_id,
        "name": "NewName",
        "status": PetStatus.sold.value,
        "tags": ["updated"],
        "photo_urls": ["http://new.com"],
        "last_updated_at": last_updated_at
    }
    response = await client.put("/pet/", json=updated_pet_data, headers=auth_headers_fixture)

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["id"] == pet_id
    assert data["name"] == "NewName"
    assert data["status"] == PetStatus.sold.value
    assert data["tags"] == ["updated"]
    assert data["photo_urls"] == ["http://new.com"]
    assert data["updated_at"] != last_updated_at  # updated_at should change


@pytest.mark.asyncio
async def test_update_pet_not_found(client: AsyncClient, override_get_db, auth_headers_fixture: dict):
    """Test updating a non-existent pet."""
    updated_pet_data = {
        "id": 9999,
        "name": "NonExistent",
        "status": PetStatus.available.value,
        "last_updated_at": datetime.now(timezone.utc).isoformat()
    }
    response = await client.put("/pet/", json=updated_pet_data, headers=auth_headers_fixture)
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json()["detail"] == "Pet not found"


@pytest.mark.asyncio
async def test_update_pet_optimistic_lock_failure(client: AsyncClient, override_get_db, auth_headers_fixture: dict):
    """Test updating a pet with an outdated last_updated_at timestamp."""
    # Create a pet
    pet_data = {"name": "LockTest", "status": PetStatus.available.value}
    create_response = await client.post("/pet/", json=pet_data, headers=auth_headers_fixture)
    created_pet = create_response.json()
    pet_id = created_pet["id"]
    original_updated_at = created_pet["updated_at"]

    # Simulate an outdated timestamp (e.g., one second earlier)
    outdated_updated_at = (datetime.fromisoformat(original_updated_at.replace("Z", "+00:00")) - timedelta(seconds=1)).isoformat(timespec='milliseconds').replace("+00:00", "Z")


    updated_pet_data = {
        "id": pet_id,
        "name": "NewNameConflict",
        "status": PetStatus.pending.value,
        "tags": [],
        "photo_urls": [],
        "last_updated_at": outdated_updated_at # Intentionally outdated
    }
    response = await client.put("/pet/", json=updated_pet_data, headers=auth_headers_fixture)

    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.json()["detail"] == "Pet has been modified by another process. Please retrieve the latest version and try again."


@pytest.mark.asyncio
async def test_update_pet_unauthenticated(client: AsyncClient, override_get_db):
    """Test updating a pet without authentication."""
    pet_data = {"id": 1, "name": "Unauthorized", "status": "available", "last_updated_at": datetime.now(timezone.utc).isoformat()}
    response = await client.put("/pet/", json=pet_data)

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert "detail" in response.json()


@pytest.mark.asyncio
async def test_delete_pet_success(client: AsyncClient, override_get_db, auth_headers_fixture: dict):
    """Test successful soft-deletion of a pet."""
    # Create a pet
    pet_data = {"name": "ToDelete", "status": "available"}
    create_response = await client.post("/pet/", json=pet_data, headers=auth_headers_fixture)
    pet_id = create_response.json()["id"]

    response = await client.delete(f"/pet/{pet_id}", headers=auth_headers_fixture)
    assert response.status_code == status.HTTP_204_NO_CONTENT

    # Verify it's soft-deleted (GET should return 404)
    get_response = await client.get(f"/pet/{pet_id}")
    assert get_response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_delete_pet_not_found(client: AsyncClient, override_get_db, auth_headers_fixture: dict):
    """Test deleting a non-existent pet."""
    response = await client.delete("/pet/9999", headers=auth_headers_fixture)
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json()["detail"] == "Pet not found"


@pytest.mark.asyncio
async def test_delete_pet_already_deleted(client: AsyncClient, override_get_db, auth_headers_fixture: dict):
    """Test deleting an already soft-deleted pet should still return 404."""
    # Create pet
    pet_data = {"name": "DoubleDelete", "status": "available"}
    create_response = await client.post("/pet/", json=pet_data, headers=auth_headers_fixture)
    pet_id = create_response.json()["id"]

    # Delete once
    await client.delete(f"/pet/{pet_id}", headers=auth_headers_fixture)

    # Attempt to delete again
    response = await client.delete(f"/pet/{pet_id}", headers=auth_headers_fixture)
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json()["detail"] == "Pet not found"


@pytest.mark.asyncio
async def test_delete_pet_unauthenticated(client: AsyncClient, override_get_db):
    """Test deleting a pet without authentication."""
    response = await client.delete("/pet/1")

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert "detail" in response.json()