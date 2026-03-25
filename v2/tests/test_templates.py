import uuid


async def test_create_template(authed_client, mock_embedding):
    resp = await authed_client.post("/templates", json={
        "content": "Write a [topic] thread with [count] posts.",
        "description": "Thread template",
        "category": "TWITTER",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["content"] == "Write a [topic] thread with [count] posts."
    assert data["category"] == "TWITTER"
    mock_embedding.assert_called_once()


async def test_list_templates(authed_client, mock_embedding):
    await authed_client.post("/templates", json={
        "content": "T1", "category": "TWITTER",
    })
    await authed_client.post("/templates", json={
        "content": "T2", "category": "LINKEDIN",
    })
    resp = await authed_client.get("/templates")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


async def test_list_templates_filter_category(authed_client, mock_embedding):
    await authed_client.post("/templates", json={"content": "T1", "category": "TWITTER"})
    await authed_client.post("/templates", json={"content": "T2", "category": "LINKEDIN"})
    resp = await authed_client.get("/templates", params={"category": "TWITTER"})
    assert len(resp.json()) == 1
    assert resp.json()[0]["category"] == "TWITTER"


async def test_get_template(authed_client, mock_embedding):
    create = await authed_client.post("/templates", json={"content": "T", "category": "TWITTER"})
    tid = create.json()["id"]
    resp = await authed_client.get(f"/templates/{tid}")
    assert resp.status_code == 200


async def test_get_template_not_found(authed_client):
    resp = await authed_client.get(f"/templates/{uuid.uuid4()}")
    assert resp.status_code == 404


async def test_delete_template(authed_client, mock_embedding):
    create = await authed_client.post("/templates", json={"content": "T", "category": "TWITTER"})
    tid = create.json()["id"]
    resp = await authed_client.delete(f"/templates/{tid}")
    assert resp.status_code == 204


async def test_search_templates(authed_client, mock_embedding):
    await authed_client.post("/templates", json={"content": "Thread maker", "category": "TWITTER"})
    resp = await authed_client.post("/templates/search", json={
        "query": "thread",
        "limit": 5,
    })
    assert resp.status_code == 200
    assert "templates" in resp.json()
