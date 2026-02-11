import pytest
import httpx
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import models
from app.schemas.pet import PetCreate, PetStatusEnum
from app.schemas.order import OrderCreate, OrderStatusEnum

@pytest.mark.asyncio
async def test_place_order_success(client: httpx.AsyncClient, db_session: AsyncSession):
    # 1. Create a pet first
    pet_data = PetCreate(name="Orderable Pet", status=PetStatusEnum.available)
    pet_response = await client.post("/pet/", json=pet_data.model_dump())
    assert pet_response.status_code == 201
    pet_id = pet_response.json()["id"]

    # 2. Place an order for the pet
    order_data = OrderCreate(
        petId=pet_id,
        quantity=1,
        shipDate=datetime.now(timezone.utc),
        status=OrderStatusEnum.placed,
        complete=False
    )
    order_response = await client.post("/store/order", json=order_data.model_dump(by_alias=True)) # Use by_alias for shipDate
    
    assert order_response.status_code == 200
    response_data = order_response.json()
    assert response_data["petId"] == pet_id
    assert response_data["quantity"] == 1
    assert response_data["status"] == "placed"
    assert "id" in response_data
    assert "shipDate" in response_data
    assert response_data["complete"] is False

    # Verify in DB
    db_order = await db_session.get(models.Order, response_data["id"])
    assert db_order is not None
    assert db_order.pet_id == pet_id
    assert db_order.quantity == 1
    assert db_order.status == "placed"
    assert db_order.complete is False

@pytest.mark.asyncio
async def test_place_order_pet_not_found(client: httpx.AsyncClient):
    # Attempt to order a non-existent pet
    order_data = OrderCreate(petId=999999, quantity=1, status=OrderStatusEnum.placed)
    order_response = await client.post("/store/order", json=order_data.model_dump())
    
    assert order_response.status_code == 404
    assert order_response.json()["detail"] == "Pet with ID 999999 not found or is unavailable."

@pytest.mark.asyncio
async def test_place_order_invalid_quantity(client: httpx.AsyncClient):
    # Attempt to order with invalid quantity
    order_data = {"petId": 1, "quantity": 0, "status": "placed"}
    order_response = await client.post("/store/order", json=order_data)
    assert order_response.status_code == 422 # Pydantic validation error

@pytest.mark.asyncio
async def test_get_inventory(client: httpx.AsyncClient, db_session: AsyncSession):
    # Clear existing pets for predictable inventory counts (db_session is isolated per test)
    # This is implicitly handled by `conftest.py`'s `db_session` fixture rolling back.
    
    # Create some test pets
    pet1 = models.Pet(name="Inv Pet 1", status=PetStatusEnum.available.value, is_deleted=False)
    pet2 = models.Pet(name="Inv Pet 2", status=PetStatusEnum.pending.value, is_deleted=False)
    pet3 = models.Pet(name="Inv Pet 3", status=PetStatusEnum.sold.value, is_deleted=False)
    pet4 = models.Pet(name="Deleted Pet", status=PetStatusEnum.available.value, is_deleted=True) # Should not be counted
    
    db_session.add_all([pet1, pet2, pet3, pet4])
    await db_session.commit()
    await db_session.refresh(pet1)
    await db_session.refresh(pet2)
    await db_session.refresh(pet3)
    await db_session.refresh(pet4)

    inventory_response = await client.get("/store/inventory")
    
    assert inventory_response.status_code == 200
    response_data = inventory_response.json()
    assert response_data["available"] == 1
    assert response_data["pending"] == 1
    assert response_data["sold"] == 1

@pytest.mark.asyncio
async def test_get_inventory_empty(client: httpx.AsyncClient, db_session: AsyncSession):
    # No pets created, should return all zeros
    inventory_response = await client.get("/store/inventory")
    
    assert inventory_response.status_code == 200
    response_data = inventory_response.json()
    assert response_data["available"] == 0
    assert response_data["pending"] == 0
    assert response_data["sold"] == 0

@pytest.mark.asyncio
async def test_full_pet_order_flow(client: httpx.AsyncClient, db_session: AsyncSession):
    # 1. Create a Pet
    pet_data = PetCreate(name="Flow Pet", status=PetStatusEnum.available, photoUrls=["flow_url"])
    create_pet_res = await client.post("/pet/", json=pet_data.model_dump())
    assert create_pet_res.status_code == 201
    pet_id = create_pet_res.json()["id"]

    # 2. Verify Pet exists
    get_pet_res = await client.get(f"/pet/{pet_id}")
    assert get_pet_res.status_code == 200
    assert get_pet_res.json()["name"] == "Flow Pet"

    # 3. Place an Order for the Pet
    order_data = OrderCreate(petId=pet_id, quantity=3, status=OrderStatusEnum.placed)
    place_order_res = await client.post("/store/order", json=order_data.model_dump())
    assert place_order_res.status_code == 200
    order_id = place_order_res.json()["id"]

    # 4. Check Inventory (should show the pet's status)
    inventory_res = await client.get("/store/inventory")
    assert inventory_res.status_code == 200
    assert inventory_res.json()["available"] >= 1 # Could be more if other tests didn't rollback perfectly, but at least 1 from this flow

    # 5. Soft Delete the Pet
    delete_pet_res = await client.delete(f"/pet/{pet_id}")
    assert delete_pet_res.status_code == 204

    # 6. Verify Pet is soft-deleted (GET should fail)
    get_deleted_pet_res = await client.get(f"/pet/{pet_id}")
    assert get_deleted_pet_res.status_code == 404

    # 7. Check Inventory again (should not count the deleted pet)
    inventory_after_delete_res = await client.get("/store/inventory")
    assert inventory_after_delete_res.status_code == 200
    # Assuming initial setup was clean, this should now be 0 if this was the only pet
    # If other pets are present, it should be 1 less than before.
    # For robust test, store previous count and compare.
    # For now, a basic check that it's not the initial value.
    assert inventory_after_delete_res.json()["available"] < inventory_res.json()["available"] if inventory_res.json()["available"] > 0 else True