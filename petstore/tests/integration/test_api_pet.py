import pytest
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import models
from app.schemas.pet import PetCreate, PetUpdate, PetStatusEnum

@pytest.mark.asyncio
async def test_create_pet_success(client: httpx.AsyncClient, db_session: AsyncSession):
    pet_data = PetCreate(name="Integration Test Pet", status=PetStatusEnum.available, photoUrls=["url1"], tags=["cute"])
    
    response = await client.post("/pet/", json=pet_data.model_dump())
    
    assert response.status_code == 201
    response_data = response.json()
    assert response_data["name"] == "Integration Test Pet"
    assert response_data["status"] == "available"
    assert response_data["photoUrls"] == ["url1"]
    assert response_data["tags"] == ["cute"]
    assert "id" in response_data

    # Verify in DB
    db_pet = await db_session.get(models.Pet, response_data["id"])
    assert db_pet is not None
    assert db_pet.name == "Integration Test Pet"
    assert db_pet.status == "available"
    assert db_pet.photo_urls == ["url1"]
    assert db_pet.tags == ["cute"]
    assert db_pet.is_deleted is False

@pytest.mark.asyncio
async def test_create_pet_invalid_data(client: httpx.AsyncClient):
    invalid_pet_data = {"name": "", "status": "invalid_status"} # Name empty, status invalid
    response = await client.post("/pet/", json=invalid_pet_data)
    assert response.status_code == 422 # Pydantic validation error

@pytest.mark.asyncio
async def test_get_pet_by_id_success(client: httpx.AsyncClient, db_session: AsyncSession):
    new_pet = models.Pet(name="Get Test Pet", status=PetStatusEnum.pending.value)
    db_session.add(new_pet)
    await db_session.commit()
    await db_session.refresh(new_pet)
    
    response = await client.get(f"/pet/{new_pet.id}")
    
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["id"] == new_pet.id
    assert response_data["name"] == "Get Test Pet"
    assert response_data["status"] == "pending"

@pytest.mark.asyncio
async def test_get_pet_by_id_not_found(client: httpx.AsyncClient):
    response = await client.get("/pet/999999") # Non-existent ID
    assert response.status_code == 404
    assert response.json()["detail"] == "Pet with ID 999999 not found."

@pytest.mark.asyncio
async def test_get_pet_by_id_soft_deleted(client: httpx.AsyncClient, db_session: AsyncSession):
    deleted_pet = models.Pet(name="Deleted Pet", status=PetStatusEnum.sold.value, is_deleted=True)
    db_session.add(deleted_pet)
    await db_session.commit()
    await db_session.refresh(deleted_pet)

    response = await client.get(f"/pet/{deleted_pet.id}")
    assert response.status_code == 404
    assert response.json()["detail"] == f"Pet with ID {deleted_pet.id} not found."

@pytest.mark.asyncio
async def test_update_pet_success(client: httpx.AsyncClient, db_session: AsyncSession):
    existing_pet = models.Pet(name="Update Test Pet", status=PetStatusEnum.available.value, tags=["old"])
    db_session.add(existing_pet)
    await db_session.commit()
    await db_session.refresh(existing_pet)

    update_data = PetUpdate(
        id=existing_pet.id,
        name="Updated Name",
        status=PetStatusEnum.sold,
        photoUrls=["new_url"],
        tags=["new", "tag"]
    )
    
    response = await client.put("/pet/", json=update_data.model_dump())
    
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["id"] == existing_pet.id
    assert response_data["name"] == "Updated Name"
    assert response_data["status"] == "sold"
    assert response_data["photoUrls"] == ["new_url"]
    assert response_data["tags"] == ["new", "tag"]

    # Verify in DB
    db_pet = await db_session.get(models.Pet, existing_pet.id)
    assert db_pet is not None
    assert db_pet.name == "Updated Name"
    assert db_pet.status == "sold"
    assert db_pet.photo_urls == ["new_url"]
    assert db_pet.tags == ["new", "tag"]

@pytest.mark.asyncio
async def test_update_pet_partial_success(client: httpx.AsyncClient, db_session: AsyncSession):
    existing_pet = models.Pet(name="Partial Update", status=PetStatusEnum.available.value, tags=["initial"], photo_urls=["initial_url"])
    db_session.add(existing_pet)
    await db_session.commit()
    await db_session.refresh(existing_pet)

    update_data = PetUpdate(
        id=existing_pet.id,
        name="Only Name Changed",
        tags=["new_tags_only"]
    )
    
    response = await client.put("/pet/", json=update_data.model_dump())
    
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["id"] == existing_pet.id
    assert response_data["name"] == "Only Name Changed"
    assert response_data["status"] == existing_pet.status # Should remain unchanged
    assert response_data["photoUrls"] == existing_pet.photo_urls # Should remain unchanged
    assert response_data["tags"] == ["new_tags_only"]

    # Verify in DB
    db_pet = await db_session.get(models.Pet, existing_pet.id)
    assert db_pet.name == "Only Name Changed"
    assert db_pet.status == existing_pet.status
    assert db_pet.photo_urls == existing_pet.photo_urls
    assert db_pet.tags == ["new_tags_only"]

@pytest.mark.asyncio
async def test_update_pet_not_found(client: httpx.AsyncClient):
    update_data = PetUpdate(id=999999, name="Non Existent")
    response = await client.put("/pet/", json=update_data.model_dump())
    assert response.status_code == 404
    assert response.json()["detail"] == "Pet with ID 999999 not found."

@pytest.mark.asyncio
async def test_delete_pet_success(client: httpx.AsyncClient, db_session: AsyncSession):
    pet_to_delete = models.Pet(name="Delete Me", status=PetStatusEnum.available.value)
    db_session.add(pet_to_delete)
    await db_session.commit()
    await db_session.refresh(pet_to_delete)
    
    response = await client.delete(f"/pet/{pet_to_delete.id}")
    
    assert response.status_code == 204
    assert response.content == b''

    # Verify in DB
    db_pet = await db_session.get(models.Pet, pet_to_delete.id)
    assert db_pet is not None
    assert db_pet.is_deleted is True

    # Verify GET now returns 404
    get_response = await client.get(f"/pet/{pet_to_delete.id}")
    assert get_response.status_code == 404

@pytest.mark.asyncio
async def test_delete_pet_not_found(client: httpx.AsyncClient):
    response = await client.delete("/pet/999999") # Non-existent ID
    assert response.status_code == 404
    assert response.json()["detail"] == "Pet with ID 999999 not found."

@pytest.mark.asyncio
async def test_delete_pet_already_deleted(client: httpx.AsyncClient, db_session: AsyncSession):
    already_deleted_pet = models.Pet(name="Already Gone", status=PetStatusEnum.available.value, is_deleted=True)
    db_session.add(already_deleted_pet)
    await db_session.commit()
    await db_session.refresh(already_deleted_pet)

    response = await client.delete(f"/pet/{already_deleted_pet.id}")
    assert response.status_code == 204 # Should be idempotent and still return 204

    db_pet = await db_session.get(models.Pet, already_deleted_pet.id)
    assert db_pet.is_deleted is True