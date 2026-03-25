import uuid


async def test_create_brand(authed_client):
    resp = await authed_client.post("/brands", json={
        "name": "Bold Brand",
        "voice_guidelines": "Be bold and direct.",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Bold Brand"
    assert data["voice_guidelines"] == "Be bold and direct."


async def test_list_brands(authed_client):
    await authed_client.post("/brands", json={"name": "B1", "voice_guidelines": "g1"})
    await authed_client.post("/brands", json={"name": "B2", "voice_guidelines": "g2"})
    resp = await authed_client.get("/brands")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


async def test_list_brands_pagination(authed_client):
    for i in range(3):
        await authed_client.post("/brands", json={"name": f"B{i}", "voice_guidelines": "g"})
    resp = await authed_client.get("/brands", params={"limit": 2, "offset": 0})
    assert len(resp.json()) == 2
    resp = await authed_client.get("/brands", params={"limit": 2, "offset": 2})
    assert len(resp.json()) == 1


async def test_get_brand(authed_client):
    create = await authed_client.post("/brands", json={"name": "B", "voice_guidelines": "g"})
    brand_id = create.json()["id"]
    resp = await authed_client.get(f"/brands/{brand_id}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "B"


async def test_get_brand_not_found(authed_client):
    resp = await authed_client.get(f"/brands/{uuid.uuid4()}")
    assert resp.status_code == 404


async def test_update_brand(authed_client):
    create = await authed_client.post("/brands", json={"name": "Old", "voice_guidelines": "g"})
    brand_id = create.json()["id"]
    resp = await authed_client.put(f"/brands/{brand_id}", json={"name": "New"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "New"
    assert resp.json()["voice_guidelines"] == "g"


async def test_delete_brand(authed_client):
    create = await authed_client.post("/brands", json={"name": "Del", "voice_guidelines": "g"})
    brand_id = create.json()["id"]
    resp = await authed_client.delete(f"/brands/{brand_id}")
    assert resp.status_code == 204
    resp = await authed_client.get(f"/brands/{brand_id}")
    assert resp.status_code == 404
