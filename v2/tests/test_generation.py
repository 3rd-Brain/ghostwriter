import asyncio

SAMPLE_STEP = {
    "order": 1,
    "name": "draft",
    "model": "claude-haiku-4-5-20251001",
    "system_prompt": "You are a writer.",
    "user_prompt": "Write about {content}",
}


async def test_generate(authed_client, mock_provider):
    # Create a workflow first
    wf_resp = await authed_client.post("/workflows", json={
        "name": "Gen Flow",
        "steps": [SAMPLE_STEP],
    })
    wf_id = wf_resp.json()["id"]

    resp = await authed_client.post("/generate", json={
        "workflow_id": wf_id,
        "content": "AI trends in 2026",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "started"
    assert data["template_count"] == 1

    # Let background task complete
    await asyncio.sleep(0.2)

    # Verify content was created
    list_resp = await authed_client.get("/generated-content")
    items = list_resp.json()
    assert len(items) >= 1
    assert items[0]["output"] == "Generated output"


async def test_generate_workflow_not_found(authed_client):
    import uuid
    resp = await authed_client.post("/generate", json={
        "workflow_id": str(uuid.uuid4()),
        "content": "test",
    })
    assert resp.status_code == 404


async def test_list_generated_content(authed_client, mock_provider):
    wf_resp = await authed_client.post("/workflows", json={
        "name": "Gen Flow",
        "steps": [SAMPLE_STEP],
    })
    wf_id = wf_resp.json()["id"]

    await authed_client.post("/generate", json={
        "workflow_id": wf_id,
        "content": "test",
    })

    # Let background task complete
    await asyncio.sleep(0.2)

    resp = await authed_client.get("/generated-content")
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


async def test_get_generated_content_by_id(authed_client, mock_provider):
    wf_resp = await authed_client.post("/workflows", json={
        "name": "Gen Flow",
        "steps": [SAMPLE_STEP],
    })
    wf_id = wf_resp.json()["id"]

    await authed_client.post("/generate", json={
        "workflow_id": wf_id,
        "content": "test",
    })

    # Let background task complete
    await asyncio.sleep(0.2)

    list_resp = await authed_client.get("/generated-content")
    gen_id = list_resp.json()[0]["id"]

    resp = await authed_client.get(f"/generated-content/{gen_id}")
    assert resp.status_code == 200
    assert resp.json()["output"] == "Generated output"
