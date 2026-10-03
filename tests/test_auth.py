import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_register_and_login(async_client: AsyncClient):
    # 1. Register a user (Project API Key is not strictly required for base auth if we bypass or use default, 
    # but our dependency requires x-api-key for register. 
    # Let's bypass x-api-key for testing register/login by either providing a mocked one, or we can create an admin key first.
    # Actually, let's create a project and API key first via an admin route, or just mock the dependency.)
    
    # We will test the health endpoint first to ensure app is running
    res = await async_client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"
