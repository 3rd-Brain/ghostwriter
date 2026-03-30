# Ghostwriter MCP Server Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add an MCP server to Ghostwriter V2 using `fastapi-mcp`, exposing all API endpoints as native MCP tools for AI agent consumption via Streamable HTTP transport.

**Architecture:** `fastapi-mcp` auto-generates MCP tools from existing FastAPI routes using the ASGI interface. Auth is handled via `AuthConfig` with the existing `get_current_account` dependency. One line change in `main.py` cleans up tool names. File upload excluded via `exclude_operations`. MCP SKILL.md created for agent reference.

**Tech Stack:** `fastapi-mcp==0.4.0`, existing FastAPI app, Bearer token auth passthrough.

---

### Task 1: Add fastapi-mcp dependency

**Files:**
- Modify: `v2/requirements.txt`

**Step 1: Add the dependency**

Add `fastapi-mcp==0.4.0` to the end of `v2/requirements.txt`:

```
fastapi-mcp==0.4.0
```

**Step 2: Install it**

Run: `cd v2 && pip install -r requirements.txt`

**Step 3: Commit**

```bash
git add v2/requirements.txt
git commit -m "feat(v2): add fastapi-mcp dependency for MCP server"
```

---

### Task 2: Clean up operation IDs for tool naming

`fastapi-mcp` uses FastAPI's `operationId` as the MCP tool name. By default, FastAPI generates ugly names like `list_brands_brands_get`. We fix this by telling FastAPI to use the function name directly.

**Files:**
- Modify: `v2/app/main.py`

**Step 1: Add generate_unique_id_function to FastAPI constructor**

In `v2/app/main.py`, add a helper function and pass it to the `FastAPI()` constructor:

```python
from fastapi.routing import APIRoute

def use_route_names_as_operation_ids(route: APIRoute) -> str:
    return route.name

app = FastAPI(
    title="Ghostwriter",
    version="2.0.0",
    description="AI content generation API. Ingest source content, define brand voices and templates, then generate social posts using multi-step LLM workflows.",
    lifespan=lifespan,
    generate_unique_id_function=use_route_names_as_operation_ids,
)
```

**Step 2: Verify operation IDs are clean**

Run:
```bash
cd v2 && python -c "
from app.main import app
schema = app.openapi()
for path, methods in sorted(schema['paths'].items()):
    for method, details in methods.items():
        print(f'{details.get(\"operationId\"):40s} {method.upper():6s} {path}')
"
```

Expected: clean names like `list_brands`, `create_workflow`, `generate`, `templatize` (matching function names).

**Step 3: Commit**

```bash
git add v2/app/main.py
git commit -m "feat(v2): use function names as operation IDs for clean MCP tool names"
```

---

### Task 3: Mount MCP server with auth

**Files:**
- Modify: `v2/app/main.py`

**Step 1: Add MCP server setup after router registration**

At the bottom of `v2/app/main.py`, after all `app.include_router(...)` calls and the health endpoint, add:

```python
from fastapi import Depends
from fastapi_mcp import FastApiMCP, AuthConfig
from app.auth import get_current_account

mcp = FastApiMCP(
    app,
    name="Ghostwriter MCP",
    description="AI content generation tools. Manage brands, workflows, templates, source content, and generate social posts via multi-step LLM workflows.",
    exclude_operations=["upload_file", "health"],
    auth_config=AuthConfig(
        dependencies=[Depends(get_current_account)],
    ) if settings.auth_enabled else None,
)
mcp.mount_http()
```

Key decisions:
- `exclude_operations=["upload_file", "health"]` — file upload is REST-only (MCP can't pass binary files), health check isn't a useful tool.
- `auth_config` only set when `auth_enabled=True` — in self-hosted no-auth mode, MCP tools work without a Bearer token.
- Tool descriptions come from the existing `summary` and `description` fields already on each route.

**Step 2: Verify MCP endpoint responds**

Run the app:
```bash
cd v2 && uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Then in another terminal:
```bash
curl http://localhost:8000/mcp
```

Expected: MCP endpoint responds (may return SSE stream or protocol handshake).

**Step 3: Commit**

```bash
git add v2/app/main.py
git commit -m "feat(v2): mount MCP server with auth and endpoint filtering"
```

---

### Task 4: Write MCP SKILL.md for agent reference

**Files:**
- Create: `v2/skills/ghostwriter-v2-mcp/SKILL.md`

**Step 1: Write the SKILL.md**

Create `v2/skills/ghostwriter-v2-mcp/SKILL.md` with the following content. This mirrors the structure of the existing REST API skill but frames everything as MCP tool calls:

```markdown
---
name: ghostwriter-v2-mcp
description: Use when generating social media content, managing brand voices, working with content templates, importing source material, or calling any Ghostwriter V2 tool. Reference for all MCP tools, input resolution modes, and multi-step workflow execution.
---

# Ghostwriter V2 MCP Tools

AI-powered content generation engine. You provide source content, brand voice, templates, and a workflow recipe — it runs a multi-step LLM pipeline and returns generated posts.

## Connection

Connect to the Ghostwriter MCP server:

```json
{
  "mcpServers": {
    "ghostwriter": {
      "url": "https://your-server.com/mcp",
      "headers": { "Authorization": "Bearer gw_your_api_key" }
    }
  }
}
```

In self-hosted no-auth mode, omit the Authorization header.

## Resource Model

Five resource pools, one action tool:

```
Brand Voices ─── "how to sound"
Workflows    ─── "multi-step AI recipes"        ──→  generate  ──→  Generated Content
Templates    ─── "structural patterns"                (the engine)    (read-only history)
Source Content ── "raw material (vector-embedded)"
```

## Available Tools

### Accounts
| Tool | Params | What it does |
|------|--------|--------------|
| `create_account` | `name` | Create account, returns API key (auth mode only) |
| `get_me` | — | Get current account info |

### Brands
| Tool | Params | What it does |
|------|--------|--------------|
| `create_brand` | `name`, `voice_guidelines`, `sample_content?` | Create a brand voice |
| `list_brands` | `limit?`, `offset?` | List all brands |
| `get_brand` | `brand_id` | Get brand by ID |
| `update_brand` | `brand_id`, `name?`, `voice_guidelines?`, `sample_content?` | Update a brand |
| `delete_brand` | `brand_id` | Delete a brand |

### Workflows
| Tool | Params | What it does |
|------|--------|--------------|
| `create_workflow` | `name`, `description?`, `steps` | Create a generation workflow |
| `list_workflows` | `limit?`, `offset?` | List all workflows |
| `get_workflow` | `workflow_id` | Get workflow by ID |
| `update_workflow` | `workflow_id`, `name?`, `description?`, `steps?` | Update a workflow |
| `delete_workflow` | `workflow_id` | Delete a workflow |

### Templates
| Tool | Params | What it does |
|------|--------|--------------|
| `create_template` | `content`, `description?`, `category` | Create a template (auto-embedded) |
| `list_templates` | `category?`, `limit?`, `offset?` | List templates |
| `get_template` | `template_id` | Get template by ID |
| `search_templates` | `query`, `category?`, `limit?` | Semantic search for templates |
| `delete_template` | `template_id` | Delete a template |

### Source Content
| Tool | Params | What it does |
|------|--------|--------------|
| `create_source_content` | `content`, `source?`, `channel_source?`, `metadata?` | Add source content (auto-embedded) |
| `batch_import` | `items[]` | Add multiple items at once |
| `list_source_content` | `limit?`, `offset?` | List all source content |
| `search_source_content` | `query`, `limit?` | Semantic search source content |
| `import_twitter` | `profile_url`, `max_tweets?` | Import tweets (requires Apify) |
| `import_linkedin` | `profile_url`, `max_posts?` | Import LinkedIn posts (requires Apify) |
| `import_youtube_channel` | `channel_url`, `max_videos?`, `sort_by?` | Import YouTube channel transcripts (requires Apify) |
| `import_youtube_video` | `video_url` | Import single YouTube video transcript (requires Apify) |
| `delete_source_content` | `content_id` | Delete source content |

### Generation
| Tool | Params | What it does |
|------|--------|--------------|
| `generate` | `workflow_id`, `content?`, `content_query?`, `template?`, `template_query?`, `template_count?`, `brand_id?`, `provider_keys?` | Execute workflow to generate content |
| `list_generated_content` | `limit?`, `offset?` | List generation history |
| `get_generated_content` | `content_id` | Get a specific generation |

### Templatize
| Tool | Params | What it does |
|------|--------|--------------|
| `templatize` | `content`, `model?`, `provider_key?` | Extract template from example content |

## Not Available via MCP

**File upload** — Use the REST API `POST /source-content/upload` for PDF/DOCX/TXT/MD files. For text content, use the `create_source_content` or `batch_import` tools instead.

## Setup Lifecycle

Before generating, stock the system with material:

### 1. Import source content

```
# Direct text
create_source_content(content="AI is transforming healthcare...", source="blog")

# Bulk
batch_import(items=[
  {content: "First piece", source: "newsletter"},
  {content: "Second piece", source: "blog"}
])

# Twitter scrape
import_twitter(profile_url="https://x.com/handle", max_tweets=50)

# LinkedIn scrape
import_linkedin(profile_url="https://linkedin.com/in/handle", max_posts=50)

# YouTube channel
import_youtube_channel(channel_url="https://youtube.com/@channel", max_videos=20)

# YouTube single video
import_youtube_video(video_url="https://youtube.com/watch?v=abc123")
```

### 2. Define brand voice

```
create_brand(
  name="CEO Thought Leadership",
  voice_guidelines="Authoritative but approachable. Short sentences. No jargon.",
  sample_content="Optional example posts..."
)
```

### 3. Build templates (optional)

Extract a pattern from a high-performing post:
```
templatize(content="I spent 10 years building startups...")
→ "I spent [X time] [doing activity] and here's [the insight]..."
```

Store it:
```
create_template(
  content="I spent [X time] [doing activity]...",
  description="Personal experience hook",
  category="short_form"
)
```

Categories: `short_form`, `atomic`, `mid_form`.

### 4. Create a workflow

```
create_workflow(
  name="LinkedIn Thought Leadership",
  steps=[
    {order: 1, name: "draft", model: "claude-sonnet-4-6", system_prompt: "...", user_prompt: "Source: {content}\nTemplate: {template}\nVoice: {brand_voice}"},
    {order: 2, name: "refine", model: "claude-haiku-4-5-20251001", system_prompt: "Tighten this post.", user_prompt: "Draft: {prev_ai_output}\nVoice: {brand_voice}"}
  ]
)
```

**Template variables** (auto-substituted per step):
- `{content}` — resolved source content
- `{template}` — resolved template
- `{brand_voice}` — brand voice guidelines
- `{prev_ai_output}` — previous step's output

**Supported models:** `claude-*` (Anthropic), `gpt-*`/`o1*`/`o3*`/`o4*` (OpenAI), `gemini-*` (Google)

## Generation

```
generate(
  workflow_id="uuid",
  content="direct text",           // OR content_query="AI healthcare" (semantic search)
  template="I spent [X]...",       // OR template_query="personal story" (semantic search)
  template_count=3,                // how many templates = how many outputs
  brand_id="uuid",
  provider_keys={anthropic: "sk-...", openai: "sk-...", google: "..."}  // optional
)
```

`template_count: 3` = find 3 templates, run the full workflow 3x, return 3 structurally different outputs.

## Common Patterns

### Full control
```
generate(workflow_id="...", content="exact text", template="pattern", brand_id="...")
```

### Hands-off (let vector search find everything)
```
generate(workflow_id="...", content_query="AI healthcare", template_query="story hook", template_count=3, brand_id="...")
```

### Templatize then generate
```
result = templatize(content="viral post text...")
create_template(content=result.template, description="viral hook", category="short_form")
generate(workflow_id="...", content_query="my topic", template_query="viral hook", brand_id="...")
```

## Key Constraints

- Ghostwriter **generates only** — no publishing, scheduling, or analytics
- All data is account-scoped
- Source content and templates are vector-embedded at creation, cannot be updated (delete + recreate)
- Workflows can mix models across steps
- `provider_keys` are per-request, not stored
- Token usage tracked per generation for future billing
```

**Step 2: Commit**

```bash
git add v2/skills/ghostwriter-v2-mcp/SKILL.md
git commit -m "docs(v2): add MCP SKILL.md for agent tool reference"
```

---

### Task 5: Update design doc to reflect fastapi-mcp approach

**Files:**
- Modify: `docs/plans/2026-03-26-ghostwriter-mcp-design.md`

**Step 1: Add a note at the top of the design doc**

Add after the header:

```markdown
> **Implementation note:** Design originally specified manual tool wrappers using the `mcp` SDK.
> Implementation uses `fastapi-mcp==0.4.0` instead, which auto-generates MCP tools from existing
> FastAPI routes via ASGI transport. This eliminates the need for `app/mcp/server.py` and
> `app/mcp/tools.py` — the entire MCP layer is ~10 lines in `main.py`.
```

**Step 2: Commit**

```bash
git add docs/plans/2026-03-26-ghostwriter-mcp-design.md
git commit -m "docs: update MCP design doc with fastapi-mcp implementation note"
```

---

### Task 6: Test MCP server end-to-end

**Files:**
- Create: `v2/tests/test_mcp.py`

**Step 1: Write MCP endpoint test**

```python
from unittest.mock import patch, AsyncMock


async def test_mcp_endpoint_exists(client):
    """MCP endpoint should respond."""
    resp = await client.get("/mcp")
    # fastapi-mcp returns 405 for GET on streamable HTTP (expects POST)
    # or 200 for SSE — either confirms the endpoint is mounted
    assert resp.status_code in (200, 405)


async def test_mcp_tools_listed(authed_client):
    """MCP should list tools matching our endpoints."""
    # POST to /mcp with a tools/list request
    resp = await authed_client.post("/mcp", json={
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/list",
    }, headers={"Accept": "application/json", "Content-Type": "application/json"})
    # The exact response format depends on fastapi-mcp's transport
    # At minimum the endpoint should accept the request
    assert resp.status_code in (200, 202)


async def test_mcp_excludes_upload(client):
    """upload_file should not appear in MCP tools."""
    from app.main import mcp
    tool_names = [t.name for t in mcp.tools]
    assert "upload_file" not in tool_names
    assert "health" not in tool_names


async def test_mcp_includes_generate(client):
    """generate tool should appear in MCP tools."""
    from app.main import mcp
    tool_names = [t.name for t in mcp.tools]
    assert "generate" in tool_names
    assert "list_brands" in tool_names
    assert "create_workflow" in tool_names
    assert "templatize" in tool_names


async def test_mcp_tool_names_are_clean(client):
    """Tool names should be clean function names, not ugly auto-generated ones."""
    from app.main import mcp
    for tool in mcp.tools:
        # Should NOT contain path fragments like _brands_get or _post
        assert "_get" not in tool.name, f"Ugly tool name: {tool.name}"
        assert "_post" not in tool.name, f"Ugly tool name: {tool.name}"
        assert "_put" not in tool.name, f"Ugly tool name: {tool.name}"
        assert "_delete" not in tool.name, f"Ugly tool name: {tool.name}"
```

**Step 2: Run tests**

```bash
cd v2 && python -m pytest tests/test_mcp.py -v
```

**Step 3: Commit**

```bash
git add v2/tests/test_mcp.py
git commit -m "test(v2): add MCP server tests for tool discovery and filtering"
```
