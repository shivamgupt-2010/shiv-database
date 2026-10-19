import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_project_and_api_key_multi_tenant_isolation(async_client: AsyncClient):
    """
    Ensure complete multi-tenant isolation:
    - User A's projects and API keys are completely invisible to User B.
    - User B cannot create, list, or revoke API keys for User A's projects.
    - User A and User B can have distinct projects with same or different names.
    """
    # 1. Register User A
    res_a = await async_client.post("/auth/register", json={
        "email": "user_a@shiv.com",
        "username": "user_a",
        "password": "Password123!"
    })
    assert res_a.status_code == 200

    login_a = await async_client.post("/auth/login", json={
        "email_or_username": "user_a",
        "password": "Password123!"
    })
    assert login_a.status_code == 200
    token_a = login_a.json()["data"]["access_token"]
    headers_a = {"Authorization": f"Bearer {token_a}"}

    # 2. Register User B
    res_b = await async_client.post("/auth/register", json={
        "email": "user_b@shiv.com",
        "username": "user_b",
        "password": "Password123!"
    })
    assert res_b.status_code == 200

    login_b = await async_client.post("/auth/login", json={
        "email_or_username": "user_b",
        "password": "Password123!"
    })
    assert login_b.status_code == 200
    token_b = login_b.json()["data"]["access_token"]
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # 3. User A creates "Project Alpha"
    res_proj_a = await async_client.post("/projects/", json={
        "name": "Project Alpha",
        "description": "User A Private Project",
        "primary_provider": "shiv_native"
    }, headers=headers_a)
    assert res_proj_a.status_code == 200
    proj_a_id = res_proj_a.json()["data"]["id"]

    # 4. User A creates an API key in "Project Alpha"
    res_key_a = await async_client.post(f"/api-keys/{proj_a_id}", json={
        "name": "User A Production Key"
    }, headers=headers_a)
    assert res_key_a.status_code == 200
    key_a_id = res_key_a.json()["data"]["id"]

    # 5. User A lists projects -> Sees "Project Alpha"
    res_list_a = await async_client.get("/projects/", headers=headers_a)
    assert res_list_a.status_code == 200
    user_a_project_ids = [p["id"] for p in res_list_a.json()["data"]]
    assert proj_a_id in user_a_project_ids

    # 6. User B lists projects -> Must NOT see "Project Alpha"
    res_list_b = await async_client.get("/projects/", headers=headers_b)
    assert res_list_b.status_code == 200
    user_b_project_ids = [p["id"] for p in res_list_b.json()["data"]]
    assert proj_a_id not in user_b_project_ids

    # 7. User B attempts to list API keys for User A's project -> Must return 404
    res_get_keys_b = await async_client.get(f"/api-keys/{proj_a_id}", headers=headers_b)
    assert res_get_keys_b.status_code == 404

    # 8. User B attempts to create an API key in User A's project -> Must return 404
    res_create_key_b = await async_client.post(f"/api-keys/{proj_a_id}", json={
        "name": "Malicious Key Attempt"
    }, headers=headers_b)
    assert res_create_key_b.status_code == 404

    # 9. User B attempts to revoke User A's API key -> Must return 404
    res_revoke_key_b = await async_client.delete(f"/api-keys/{key_a_id}", headers=headers_b)
    assert res_revoke_key_b.status_code == 404

    # 10. User B creates their own project "Project Beta"
    res_proj_b = await async_client.post("/projects/", json={
        "name": "Project Beta",
        "description": "User B Private Project",
        "primary_provider": "shiv_native"
    }, headers=headers_b)
    assert res_proj_b.status_code == 200
    proj_b_id = res_proj_b.json()["data"]["id"]

    # 11. User B lists projects -> Sees "Project Beta", does NOT see "Project Alpha"
    res_list_b_updated = await async_client.get("/projects/", headers=headers_b)
    assert res_list_b_updated.status_code == 200
    user_b_projs = res_list_b_updated.json()["data"]
    assert any(p["id"] == proj_b_id for p in user_b_projs)
    assert not any(p["id"] == proj_a_id for p in user_b_projs)

    # 12. User A lists projects -> Sees "Project Alpha", does NOT see "Project Beta"
    res_list_a_updated = await async_client.get("/projects/", headers=headers_a)
    assert res_list_a_updated.status_code == 200
    user_a_projs = res_list_a_updated.json()["data"]
    assert any(p["id"] == proj_a_id for p in user_a_projs)
    assert not any(p["id"] == proj_b_id for p in user_a_projs)
