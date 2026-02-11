import pytest
from httpx import AsyncClient
from jsonschema import validate, ValidationError
from openapi_spec_validator import validate_spec
from fastapi import status


@pytest.mark.asyncio
async def test_openapi_spec_is_valid(client: AsyncClient):
    """
    Test that the generated OpenAPI specification is valid.
    """
    response = await client.get("/openapi.json")
    assert response.status_code == status.HTTP_200_OK
    spec = response.json()

    try:
        validate_spec(spec)
        print("OpenAPI spec is valid according to openapi-spec-validator.")
    except ValidationError as e:
        pytest.fail(f"OpenAPI spec is invalid: {e.message} at {e.path}")
    except Exception as e:
        pytest.fail(f"An unexpected error occurred during spec validation: {e}")


@pytest.mark.asyncio
async def test_post_pet_response_conforms_to_schema(client: AsyncClient, override_get_db, auth_headers_fixture: dict):
    """
    Test that POST /pet response conforms to PetResponse schema.
    """
    openapi_spec = (await client.get("/openapi.json")).json()
    pet_response_schema = openapi_spec["components"]["schemas"]["PetResponse"]

    pet_data = {
        "name": "SchemaTestPet",
        "status": "available",
        "tags": ["test"],
        "photo_urls": ["http://test.com/photo.jpg"]
    }
    response = await client.post("/pet/", json=pet_data, headers=auth_headers_fixture)
    assert response.status_code == status.HTTP_201_CREATED
    response_json = response.json()

    try:
        validate(instance=response_json, schema=pet_response_schema)
        print(f"POST /pet response conforms to schema: {response_json}")
    except ValidationError as e:
        pytest.fail(f"POST /pet response does not conform to schema: {e.message} in {e.path}")


@pytest.mark.asyncio
async def test_get_pet_by_id_response_conforms_to_schema(client: AsyncClient, override_get_db, auth_headers_fixture: dict):
    """
    Test that GET /pet/{id} response conforms to PetResponse schema.
    """
    openapi_spec = (await client.get("/openapi.json")).json()
    pet_response_schema = openapi_spec["components"]["schemas"]["PetResponse"]

    # First, create a pet to retrieve
    pet_data = {"name": "RetrievablePet", "status": "pending"}
    create_response = await client.post("/pet/", json=pet_data, headers=auth_headers_fixture)
    pet_id = create_response.json()["id"]

    response = await client.get(f"/pet/{pet_id}")
    assert response.status_code == status.HTTP_200_OK
    response_json = response.json()

    try:
        validate(instance=response_json, schema=pet_response_schema)
        print(f"GET /pet/{pet_id} response conforms to schema: {response_json}")
    except ValidationError as e:
        pytest.fail(f"GET /pet/{pet_id} response does not conform to schema: {e.message} in {e.path}")


@pytest.mark.asyncio
async def test_get_store_inventory_response_conforms_to_schema(client: AsyncClient, override_get_db):
    """
    Test that GET /store/inventory response conforms to its schema.
    """
    openapi_spec = (await client.get("/openapi.json")).json()
    # The inventory schema is defined inline for the /store/inventory endpoint.
    # We need to navigate to the response schema for this specific endpoint.
    inventory_response_schema = openapi_spec["paths"]["/store/inventory"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]

    response = await client.get("/store/inventory")
    assert response.status_code == status.HTTP_200_OK
    response_json = response.json()

    try:
        validate(instance=response_json, schema=inventory_response_schema)
        print(f"GET /store/inventory response conforms to schema: {response_json}")
    except ValidationError as e:
        pytest.fail(f"GET /store/inventory response does not conform to schema: {e.message} in {e.path}")


@pytest.mark.asyncio
async def test_post_user_response_conforms_to_schema(client: AsyncClient, override_get_db):
    """
    Test that POST /user response conforms to UserResponse schema.
    """
    openapi_spec = (await client.get("/openapi.json")).json()
    user_response_schema = openapi_spec["components"]["schemas"]["UserResponse"]

    user_data = {
        "username": "schematestuser",
        "email": "schematest@example.com",
        "password": "schematestpassword123",
        "first_name": "Schema",
        "last_name": "Test",
    }
    response = await client.post("/user/", json=user_data)
    assert response.status_code == status.HTTP_201_CREATED
    response_json = response.json()

    try:
        validate(instance=response_json, schema=user_response_schema)
        print(f"POST /user response conforms to schema: {response_json}")
    except ValidationError as e:
        pytest.fail(f"POST /user response does not conform to schema: {e.message} in {e.path}")


@pytest.mark.asyncio
async def test_get_user_login_response_conforms_to_schema(client: AsyncClient, override_get_db, test_user_fixture, test_user_data):
    """
    Test that GET /user/login response conforms to Token schema.
    """
    openapi_spec = (await client.get("/openapi.json")).json()
    token_schema = openapi_spec["components"]["schemas"]["Token"]

    response = await client.get(
        f"/user/login?username={test_user_data['username']}&password={test_user_data['password']}"
    )
    assert response.status_code == status.HTTP_200_OK
    response_json = response.json()

    try:
        validate(instance=response_json, schema=token_schema)
        print(f"GET /user/login response conforms to schema: {response_json}")
    except ValidationError as e:
        pytest.fail(f"GET /user/login response does not conform to schema: {e.message} in {e.path}")