import uuid


async def test_create_source_content(authed_client, mock_embedding):
    resp = await authed_client.post("/source-content", json={
        "content": "Some insightful content about AI.",
        "source": "blog",
        "channel_source": "MANUAL",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["content"] == "Some insightful content about AI."
    mock_embedding.assert_called_once()


async def test_list_source_content(authed_client, mock_embedding):
    await authed_client.post("/source-content", json={
        "content": "C1", "source": "blog", "channel_source": "MANUAL",
    })
    await authed_client.post("/source-content", json={
        "content": "C2", "source": "blog", "channel_source": "MANUAL",
    })
    resp = await authed_client.get("/source-content")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


async def test_list_source_content_pagination(authed_client, mock_embedding):
    for i in range(3):
        await authed_client.post("/source-content", json={
            "content": f"C{i}", "source": "blog", "channel_source": "MANUAL",
        })
    resp = await authed_client.get("/source-content", params={"limit": 2})
    assert len(resp.json()) == 2


async def test_delete_source_content(authed_client, mock_embedding):
    create = await authed_client.post("/source-content", json={
        "content": "Del", "source": "blog", "channel_source": "MANUAL",
    })
    cid = create.json()["id"]
    resp = await authed_client.delete(f"/source-content/{cid}")
    assert resp.status_code == 204


async def test_delete_source_content_not_found(authed_client):
    resp = await authed_client.delete(f"/source-content/{uuid.uuid4()}")
    assert resp.status_code == 404


async def test_search_source_content(authed_client, mock_embedding):
    await authed_client.post("/source-content", json={
        "content": "AI trends", "source": "blog", "channel_source": "MANUAL",
    })
    resp = await authed_client.post("/source-content/search", json={
        "query": "AI",
        "limit": 5,
    })
    assert resp.status_code == 200
    assert "results" in resp.json()


async def test_batch_import(authed_client, mock_embedding):
    resp = await authed_client.post("/source-content/batch", json={
        "items": [
            {"content": "B1", "source": "import", "channel_source": "MANUAL"},
            {"content": "B2", "source": "import", "channel_source": "MANUAL"},
        ]
    })
    assert resp.status_code == 201
    assert len(resp.json()) == 2
