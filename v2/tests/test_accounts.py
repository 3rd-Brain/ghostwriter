async def test_create_account(client):
    resp = await client.post("/accounts", json={"name": "Acme Corp"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["account"]["name"] == "Acme Corp"
    assert data["api_key"].startswith("gw_")


async def test_create_account_empty_name(client):
    resp = await client.post("/accounts", json={"name": ""})
    assert resp.status_code == 422


async def test_get_me(authed_client):
    resp = await authed_client.get("/accounts/me")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Test Account"


async def test_get_me_unauthenticated(client):
    resp = await client.get("/accounts/me")
    assert resp.status_code == 403


async def test_get_me_invalid_key(client):
    client.headers["Authorization"] = "Bearer gw_invalid_key"
    resp = await client.get("/accounts/me")
    assert resp.status_code == 401
