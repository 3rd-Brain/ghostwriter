import uuid


SAMPLE_STEP = {
    "order": 1,
    "name": "draft",
    "model": "claude-haiku-4-5-20251001",
    "system_prompt": "You are a writer.",
    "user_prompt": "Write about {content}",
}


async def test_create_workflow(authed_client):
    resp = await authed_client.post("/workflows", json={
        "name": "Test Flow",
        "steps": [SAMPLE_STEP],
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Test Flow"
    assert len(data["steps"]) == 1
    assert data["steps"][0]["name"] == "draft"


async def test_list_workflows(authed_client):
    await authed_client.post("/workflows", json={"name": "WF1", "steps": [SAMPLE_STEP]})
    resp = await authed_client.get("/workflows")
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


async def test_get_workflow(authed_client):
    create = await authed_client.post("/workflows", json={"name": "WF", "steps": [SAMPLE_STEP]})
    wf_id = create.json()["id"]
    resp = await authed_client.get(f"/workflows/{wf_id}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "WF"


async def test_get_workflow_not_found(authed_client):
    resp = await authed_client.get(f"/workflows/{uuid.uuid4()}")
    assert resp.status_code == 404


async def test_update_workflow(authed_client):
    create = await authed_client.post("/workflows", json={"name": "Old", "steps": [SAMPLE_STEP]})
    wf_id = create.json()["id"]
    resp = await authed_client.put(f"/workflows/{wf_id}", json={"name": "Updated"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "Updated"


async def test_update_workflow_steps(authed_client):
    create = await authed_client.post("/workflows", json={"name": "WF", "steps": [SAMPLE_STEP]})
    wf_id = create.json()["id"]
    new_step = {**SAMPLE_STEP, "name": "rewrite", "order": 1}
    resp = await authed_client.put(f"/workflows/{wf_id}", json={"steps": [new_step]})
    assert resp.status_code == 200
    assert resp.json()["steps"][0]["name"] == "rewrite"


async def test_delete_workflow(authed_client):
    create = await authed_client.post("/workflows", json={"name": "Del", "steps": [SAMPLE_STEP]})
    wf_id = create.json()["id"]
    resp = await authed_client.delete(f"/workflows/{wf_id}")
    assert resp.status_code == 204


async def test_workflow_step_validation(authed_client):
    bad_step = {**SAMPLE_STEP, "max_tokens": 0}
    resp = await authed_client.post("/workflows", json={"name": "Bad", "steps": [bad_step]})
    assert resp.status_code == 422


async def test_workflow_step_temperature_validation(authed_client):
    bad_step = {**SAMPLE_STEP, "temperature": 3.0}
    resp = await authed_client.post("/workflows", json={"name": "Bad", "steps": [bad_step]})
    assert resp.status_code == 422
