import pytest
from httpx import AsyncClient
from fastapi import status
from datetime import datetime, timezone, timedelta

from petstore.app.schemas.common import PetStatus, OrderStatus


@pytest.mark.asyncio
async def test_place_order_success(client: AsyncClient, override_get_db, auth_headers_fixture: dict):
    """Test successful placement of an order."""
    # First, create a pet to order
    pet_data = {"name": "Orderable Pet", "status": PetStatus.available.value}
    create_pet_response = await client.post("/pet/", json=pet_data, headers=auth_headers_fixture)
    pet_id = create_pet_response.json()["id"]

    order_data = {
        "pet_id": pet_id,
        "quantity": 1,
        "status": OrderStatus.placed.value,
        "complete": False
    }
    response = await client.post("/store/order", json=order_data, headers=auth_headers_fixture)

    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["pet_id"] == pet_id
    assert data["quantity"] == 1
    assert data["status"] == OrderStatus.placed.value
    assert data["id"] > 0
    assert "created_at" in data
    assert "updated_at" in data


@pytest.mark.asyncio
async def test_place_order_pet_not_found(client: AsyncClient, override_get_db, auth_headers_fixture: dict):
    """Test placing an order for a non-existent pet."""
    order_data = {
        "pet_id": 9999,  # Non-existent pet ID
        "quantity": 1
    }
    response = await client.post("/store/order", json=order_data, headers=auth_headers_fixture)

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json()["detail"] == "Pet not found"


@pytest.mark.asyncio
async def test_place_order_soft_deleted_pet(client: AsyncClient, override_get_db, auth_headers_fixture: dict):
    """Test placing an order for a soft-deleted pet should return 404."""
    # Create and then delete a pet
    pet_data = {"name": "Deleted Pet For Order", "status": PetStatus.available.value}
    create_pet_response = await client.post("/pet/", json=pet_data, headers=auth_headers_fixture)
    pet_id = create_pet_response.json()["id"]
    await client.delete(f"/pet/{pet_id}", headers=auth_headers_fixture)

    order_data = {
        "pet_id": pet_id,
        "quantity": 1
    }
    response = await client.post("/store/order", json=order_data, headers=auth_headers_fixture)

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json()["detail"] == "Pet not found"


@pytest.mark.asyncio
async def test_place_order_invalid_quantity(client: AsyncClient, override_get_db, auth_headers_fixture: dict):
    """Test placing an order with invalid quantity."""
    # First, create a pet
    pet_data = {"name": "Valid Pet", "status": PetStatus.available.value}
    create_pet_response = await client.post("/pet/", json=pet_data, headers=auth_headers_fixture)
    pet_id = create_pet_response.json()["id"]

    order_data = {
        "pet_id": pet_id,
        "quantity": 0  # Invalid quantity
    }
    response = await client.post("/store/order", json=order_data, headers=auth_headers_fixture)

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert "quantity" in response.json()["detail"][0]["loc"]


@pytest.mark.asyncio
async def test_place_order_unauthenticated(client: AsyncClient, override_get_db):
    """Test placing an order without authentication."""
    order_data = {
        "pet_id": 1,
        "quantity": 1
    }
    response = await client.post("/store/order", json=order_data)

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert "detail" in response.json()


@pytest.mark.asyncio
async def test_get_inventory_empty(client: AsyncClient, override_get_db):
    """Test retrieving inventory when no pets exist."""
    response = await client.get("/store/inventory")

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"available": 0, "pending": 0, "sold": 0}


@pytest.mark.asyncio
async def test_get_inventory_with_pets(client: AsyncClient, override_get_db, auth_headers_fixture: dict):
    """Test retrieving inventory with various pets."""
    # Create pets with different statuses
    await client.post("/pet/", json={"name": "Pet1", "status": PetStatus.available.value}, headers=auth_headers_fixture)
    await client.post("/pet/", json={"name": "Pet2", "status": PetStatus.available.value}, headers=auth_headers_fixture)
    await client.post("/pet/", json={"name": "Pet3", "status": PetStatus.pending.value}, headers=auth_headers_fixture)
    await client.post("/pet/", json={"name": "Pet4", "status": PetStatus.sold.value}, headers=auth_headers_fixture)

    response = await client.get("/store/inventory")

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"available": 2, "pending": 1, "sold": 1}


@pytest.mark.asyncio
async def test_get_inventory_with_soft_deleted_pets(client: AsyncClient, override_get_db, auth_headers_fixture: dict):
    """Test soft-deleted pets are not included in inventory."""
    # Create an available pet
    create_response = await client.post("/pet/", json={"name": "Active Pet", "status": PetStatus.available.value}, headers=auth_headers_fixture)
    active_pet_id = create_response.json()["id"]

    # Create a pet and soft-delete it
    create_response_deleted = await client.post("/pet/", json={"name": "Deleted Pet", "status": PetStatus.available.value}, headers=auth_headers_fixture)
    deleted_pet_id = create_response_deleted.json()["id"]
    await client.delete(f"/pet/{deleted_pet_id}", headers=auth_headers_fixture)

    response = await client.get("/store/inventory")

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"available": 1, "pending": 0, "sold": 0} # Only the active pet should be counted