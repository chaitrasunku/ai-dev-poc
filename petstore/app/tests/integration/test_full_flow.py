import pytest
from httpx import AsyncClient
from fastapi import status
from datetime import datetime, timezone, timedelta

from petstore.app.database.session import async_get_db
from petstore.app.schemas.common import PetStatus, OrderStatus
from petstore.app.models.pet import Pet
from petstore.app.models.order import Order


@pytest.mark.asyncio
async def test_pet_order_inventory_flow(client: AsyncClient, override_get_db, auth_headers_fixture: dict):
    """
    Integration test for a full workflow: Create Pet -> Get Pet -> Place Order -> Check Inventory -> Update Pet -> Check Inventory -> Delete Pet -> Verify Delete.
    """
    # 1. Create a Pet via POST /pet
    pet_create_data = {
        "name": "IntegrationTestPet",
        "status": PetStatus.available.value,
        "tags": ["friendly", "cute"],
        "photo_urls": ["http://example.com/integration_pet.jpg"]
    }
    post_pet_response = await client.post("/pet/", json=pet_create_data, headers=auth_headers_fixture)
    assert post_pet_response.status_code == status.HTTP_201_CREATED
    created_pet = post_pet_response.json()
    pet_id = created_pet["id"]
    pet_updated_at = created_pet["updated_at"]
    print(f"Created Pet: {created_pet}")

    # 2. Retrieve the pet's ID and updated_at, verify pet exists via GET /pet/{id}
    get_pet_response = await client.get(f"/pet/{pet_id}")
    assert get_pet_response.status_code == status.HTTP_200_OK
    retrieved_pet = get_pet_response.json()
    assert retrieved_pet["id"] == pet_id
    assert retrieved_pet["name"] == pet_create_data["name"]
    assert retrieved_pet["status"] == pet_create_data["status"]
    print(f"Retrieved Pet: {retrieved_pet}")

    # 3. Place an Order for this pet via POST /store/order
    order_create_data = {
        "pet_id": pet_id,
        "quantity": 2,
        "status": OrderStatus.placed.value,
        "complete": False
    }
    post_order_response = await client.post("/store/order", json=order_create_data, headers=auth_headers_fixture)
    assert post_order_response.status_code == status.HTTP_201_CREATED
    created_order = post_order_response.json()
    order_id = created_order["id"]
    assert created_order["pet_id"] == pet_id
    assert created_order["quantity"] == order_create_data["quantity"]
    print(f"Created Order: {created_order}")

    # 4. Verify the order exists (optional: directly from DB or via a GET /store/order/{id} if implemented)
    # For now, we trust the 201 response and subsequent inventory check.

    # 5. Check the Inventory via GET /store/inventory to confirm counts are updated
    inventory_response_1 = await client.get("/store/inventory")
    assert inventory_response_1.status_code == status.HTTP_200_OK
    inventory_1 = inventory_response_1.json()
    assert inventory_1.get(PetStatus.available.value, 0) >= 1 # At least one available pet (the one we created)
    print(f"Inventory after creating pet and order: {inventory_1}")

    # 6. Update the pet's status (e.g., to 'sold') via PUT /pet using the retrieved `updated_at` for optimistic locking
    pet_update_data = {
        "id": pet_id,
        "name": "IntegrationTestPet Updated",
        "status": PetStatus.sold.value, # Change status to sold
        "tags": ["friendly", "cute", "sold"],
        "photo_urls": ["http://example.com/integration_pet_updated.jpg"],
        "last_updated_at": pet_updated_at # Use the original updated_at for optimistic locking
    }
    put_pet_response = await client.put("/pet/", json=pet_update_data, headers=auth_headers_fixture)
    assert put_pet_response.status_code == status.HTTP_200_OK
    updated_pet = put_pet_response.json()
    assert updated_pet["id"] == pet_id
    assert updated_pet["name"] == pet_update_data["name"]
    assert updated_pet["status"] == pet_update_data["status"]
    assert updated_pet["updated_at"] != pet_updated_at # updated_at should be different
    print(f"Updated Pet: {updated_pet}")

    # 7. Check the Inventory again to see counts reflect the change
    inventory_response_2 = await client.get("/store/inventory")
    assert inventory_response_2.status_code == status.HTTP_200_OK
    inventory_2 = inventory_response_2.json()
    assert inventory_2.get(PetStatus.available.value, 0) == 0 # It was available, now it's sold
    assert inventory_2.get(PetStatus.sold.value, 0) >= 1 # Now it's in sold
    print(f"Inventory after updating pet status to sold: {inventory_2}")

    # 8. Delete the pet via DELETE /pet/{id}
    delete_pet_response = await client.delete(f"/pet/{pet_id}", headers=auth_headers_fixture)
    assert delete_pet_response.status_code == status.HTTP_204_NO_CONTENT
    print(f"Deleted Pet with ID: {pet_id}")

    # 9. Verify the pet is soft-deleted (GET /pet/{id} returns 404)
    verify_delete_response = await client.get(f"/pet/{pet_id}")
    assert verify_delete_response.status_code == status.HTTP_404_NOT_FOUND
    assert verify_delete_response.json()["detail"] == "Pet not found"
    print(f"Verified Pet ID {pet_id} is soft-deleted.")

    # Check inventory again to confirm deleted pet is not counted
    inventory_response_3 = await client.get("/store/inventory")
    assert inventory_response_3.status_code == status.HTTP_200_OK
    inventory_3 = inventory_response_3.json()
    assert inventory_3.get(PetStatus.sold.value, 0) == 0 # Soft-deleted pet should not be counted
    print(f"Inventory after soft-deleting pet: {inventory_3}")