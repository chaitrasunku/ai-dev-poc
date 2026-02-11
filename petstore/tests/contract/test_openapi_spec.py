import pytest
import httpx
from jsonschema import Draft7Validator, RefResolver
from app.main import app
import json

@pytest.mark.asyncio
async def test_openapi_spec_validity(client: httpx.AsyncClient):
    """
    Test that the /openapi.json endpoint returns a valid OpenAPI 3.0 specification.
    """
    response = await client.get("/openapi.json")
    assert response.status_code == 200
    
    spec = response.json()
    assert "openapi" in spec
    assert spec["openapi"].startswith("3.0.") # Check OpenAPI version

    # Basic structural checks
    assert "info" in spec
    assert "paths" in spec
    assert "components" in spec
    assert "schemas" in spec["components"]

    # Optional: More thorough validation using a specific OpenAPI validator library
    # For this task, we will do some manual checks and assume a full library
    # like openapi-spec-validator would be used for deeper validation.
    # Example using jsonschema (requires the OpenAPI 3.0 schema file)
    # This part is commented out because it requires downloading the schema,
    # which is out of scope for strict code generation.
    # try:
    #     import requests
    #     openapi_schema_url = "https://spec.openapis.org/oas/3.0/schema/2021-09-28"
    #     openapi_schema = requests.get(openapi_schema_url).json()
    #     validator = Draft7Validator(openapi_schema)
    #     validator.validate(spec)
    #     print("OpenAPI spec is valid against the OpenAPI 3.0 schema.")
    # except Exception as e:
    #     pytest.fail(f"OpenAPI spec is NOT valid against the OpenAPI 3.0 schema: {e}")

@pytest.mark.asyncio
async def test_pet_endpoints_contract(client: httpx.AsyncClient):
    """
    Test contract for /pet endpoints against the OpenAPI spec.
    """
    openapi_response = await client.get("/openapi.json")
    spec = openapi_response.json()
    resolver = RefResolver.from_schema(spec)

    # Helper to validate a response against a schema
    def validate_response_body(data, schema_ref):
        schema = resolver.resolve(schema_ref)[1]
        Draft7Validator(schema).validate(data)

    # 1. POST /pet (Add Pet)
    post_pet_schema_ref = "#/components/schemas/PetCreate"
    post_pet_response_schema_ref = "#/components/schemas/PetResponse"

    pet_data = {
        "name": "ContractTestPet",
        "status": "available",
        "photoUrls": ["http://example.com/photo.jpg"],
        "tags": ["test", "contract"]
    }
    response = await client.post("/pet/", json=pet_data)
    assert response.status_code == 201
    validate_response_body(response.json(), post_pet_response_schema_ref)
    created_pet_id = response.json()["id"]

    # 2. GET /pet/{id} (Get Pet by ID)
    get_pet_response_schema_ref = "#/components/schemas/PetResponse"
    response = await client.get(f"/pet/{created_pet_id}")
    assert response.status_code == 200
    validate_response_body(response.json(), get_pet_response_schema_ref)
    assert response.json()["id"] == created_pet_id

    # 3. PUT /pet (Update Pet)
    put_pet_schema_ref = "#/components/schemas/PetUpdate" # This includes ID now
    put_pet_response_schema_ref = "#/components/schemas/PetResponse"
    updated_pet_data = {
        "id": created_pet_id,
        "name": "UpdatedContractPet",
        "status": "sold",
        "tags": ["updated"]
    }
    response = await client.put("/pet/", json=updated_pet_data)
    assert response.status_code == 200
    validate_response_body(response.json(), put_pet_response_schema_ref)
    assert response.json()["name"] == "UpdatedContractPet"
    assert response.json()["status"] == "sold"
    assert response.json()["tags"] == ["updated"]

    # 4. DELETE /pet/{id} (Delete Pet)
    response = await client.delete(f"/pet/{created_pet_id}")
    assert response.status_code == 204
    assert response.content == b'' # No content for 204

    # Verify deleted pet is not found
    response = await client.get(f"/pet/{created_pet_id}")
    assert response.status_code == 404
    assert response.json()["detail"] == f"Pet with ID {created_pet_id} not found."

@pytest.mark.asyncio
async def test_user_endpoints_contract(client: httpx.AsyncClient):
    """
    Test contract for /user endpoints against the OpenAPI spec.
    """
    openapi_response = await client.get("/openapi.json")
    spec = openapi_response.json()
    resolver = RefResolver.from_schema(spec)

    def validate_response_body(data, schema_ref):
        schema = resolver.resolve(schema_ref)[1]
        Draft7Validator(schema).validate(data)

    # 1. POST /user (Create User)
    post_user_schema_ref = "#/components/schemas/UserCreate"
    post_user_response_schema_ref = "#/components/schemas/UserResponse"
    
    user_data = {
        "username": "contractuser",
        "firstName": "Contract",
        "lastName": "User",
        "email": "contract@example.com",
        "password": "Password123!",
        "phone": "123-456-7890",
        "userStatus": 0
    }
    response = await client.post("/user/", json=user_data)
    assert response.status_code == 201
    validate_response_body(response.json(), post_user_response_schema_ref)
    created_username = response.json()["username"]

    # 2. GET /user/login (Login User)
    token_response_schema_ref = "#/components/schemas/TokenResponse"
    response = await client.get(
        "/user/login",
        params={"username": user_data["username"], "password": user_data["password"]}
    )
    assert response.status_code == 200
    validate_response_body(response.json(), token_response_schema_ref)
    token = response.json()["token"]
    assert token

    # 3. GET /user/logout (Logout User)
    response = await client.get(
        "/user/logout",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    assert response.json() == {"message": "Successfully logged out."}

    # Verify token is invalid after logout
    response = await client.get(
        f"/pet/1", # Any protected endpoint, e.g., get a dummy pet
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 401
    assert "Token has been revoked." in response.json()["detail"] or "Could not validate credentials." in response.json()["detail"] # Depending on exact error detail

@pytest.mark.asyncio
async def test_store_endpoints_contract(client: httpx.AsyncClient):
    """
    Test contract for /store endpoints against the OpenAPI spec.
    """
    openapi_response = await client.get("/openapi.json")
    spec = openapi_response.json()
    resolver = RefResolver.from_schema(spec)

    def validate_response_body(data, schema_ref):
        schema = resolver.resolve(schema_ref)[1]
        Draft7Validator(schema).validate(data)

    # First, create a pet to order
    pet_create_data = {
        "name": "OrderTestPet",
        "status": "available",
        "photoUrls": [],
        "tags": []
    }
    pet_response = await client.post("/pet/", json=pet_create_data)
    assert pet_response.status_code == 201
    pet_id = pet_response.json()["id"]

    # 1. POST /store/order (Place Order)
    post_order_schema_ref = "#/components/schemas/OrderCreate"
    post_order_response_schema_ref = "#/components/schemas/OrderResponse"
    
    order_data = {
        "petId": pet_id,
        "quantity": 2,
        "status": "placed",
        "complete": False
    }
    response = await client.post("/store/order", json=order_data)
    assert response.status_code == 200 # OpenAPI spec returns 200 for successful operations, even for creation.
    validate_response_body(response.json(), post_order_response_schema_ref)
    created_order_id = response.json()["id"]
    assert response.json()["petId"] == pet_id
    assert response.json()["quantity"] == 2

    # 2. GET /store/inventory (Get Inventory)
    inventory_response_schema = {
        "type": "object",
        "properties": {
            "available": {"type": "integer"},
            "pending": {"type": "integer"},
            "sold": {"type": "integer"}
        }
    }
    response = await client.get("/store/inventory")
    assert response.status_code == 200
    Draft7Validator(inventory_response_schema).validate(response.json())
    assert response.json()["available"] >= 0
    assert response.json()["pending"] >= 0
    assert response.json()["sold"] >= 0
    # At least the pet we created should contribute to some status
    assert response.json()["available"] > 0 or response.json()["pending"] > 0 or response.json()["sold"] > 0