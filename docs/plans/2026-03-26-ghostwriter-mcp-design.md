# Ghostwriter V2 MCP Server Design

> **Implementation note:** Design originally specified manual tool wrappers using the `mcp` SDK.
> Implementation uses `fastapi-mcp==0.4.0` instead, which auto-generates MCP tools from existing
> FastAPI routes via ASGI transport. This eliminates the need for `app/mcp/server.py` and
> `app/mcp/tools.py` — the entire MCP layer is ~10 lines in `main.py`.

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add an MCP (Model Context Protocol) server to Ghostwriter V2 so AI agents can connect via SSE and use all Ghostwriter capabilities as native tools.

**Architecture:** Mount the MCP server inside the existing FastAPI app as an SSE endpoint. The MCP layer is a thin wrapper — it authenticates via the same API key system, gets DB sessions from the same pool, and calls the same service logic the REST endpoints use. No new business logic.

**Tech Stack:** Python `mcp` SDK, FastAPI SSE mount, existing SQLAlchemy async sessions.

---

## Architecture

```
Agent connects → GET /mcp/sse       (SSE transport, Bearer token in headers)
              → POST /mcp/messages  (tool call/response exchange)
              → Same FastAPI process, same DB, same auth
```

- **Auth:** Bearer token extracted from SSE connection headers. Authenticated once per session via existing `authenticate()` function. All tool calls in that session use the resolved account.
- **DB:** Each tool call gets a fresh `AsyncSession` from the existing `async_sessionmaker`.
- **Returns:** Tools return JSON strings. Errors return descriptive text (not exceptions) so agents can reason and retry.
- **UUIDs:** Accepted as strings in tool params, parsed internally.

## Files

**New:**
- `v2/app/mcp/server.py` — MCP server setup, SSE transport, auth extraction
- `v2/app/mcp/tools.py` — all 27 tool definitions (thin wrappers over existing logic)
- `v2/skills/ghostwriter-v2-mcp/SKILL.md` — agent-facing MCP tool reference

**Modified:**
- `v2/app/main.py` — mount MCP SSE endpoint
- `v2/requirements.txt` — add `mcp` dependency

## Tools (27 total)

### Accounts (2)
| Tool | Params | Description |
|------|--------|-------------|
| `create_account` | `name` | Create account, returns API key (unauthenticated) |
| `get_account` | — | Get current account info |

### Brands (5)
| Tool | Params | Description |
|------|--------|-------------|
| `create_brand` | `name`, `voice_guidelines`, `sample_content?` | Create a brand voice |
| `list_brands` | `limit?`, `offset?` | List all brands |
| `get_brand` | `brand_id` | Get brand by ID |
| `update_brand` | `brand_id`, `name?`, `voice_guidelines?`, `sample_content?` | Update a brand |
| `delete_brand` | `brand_id` | Delete a brand |

### Workflows (5)
| Tool | Params | Description |
|------|--------|-------------|
| `create_workflow` | `name`, `description?`, `steps` | Create a generation workflow |
| `list_workflows` | `limit?`, `offset?` | List all workflows |
| `get_workflow` | `workflow_id` | Get workflow by ID |
| `update_workflow` | `workflow_id`, `name?`, `description?`, `steps?` | Update a workflow |
| `delete_workflow` | `workflow_id` | Delete a workflow |

### Templates (5)
| Tool | Params | Description |
|------|--------|-------------|
| `create_template` | `content`, `description?`, `category` | Create a template |
| `list_templates` | `category?`, `limit?`, `offset?` | List templates |
| `get_template` | `template_id` | Get template by ID |
| `search_templates` | `query`, `category?`, `limit?` | Semantic search for templates |
| `delete_template` | `template_id` | Delete a template |

### Source Content (6)
| Tool | Params | Description |
|------|--------|-------------|
| `add_source_content` | `content`, `source`, `channel_source?`, `metadata?` | Add source content |
| `batch_import_content` | `items` | Add multiple items at once |
| `list_source_content` | `limit?`, `offset?` | List all source content |
| `search_source_content` | `query`, `limit?` | Semantic search source content |
| `import_twitter` | `profile_url`, `max_tweets?` | Import tweets from profile |
| `delete_source_content` | `content_id` | Delete source content |

### Generation (3)
| Tool | Params | Description |
|------|--------|-------------|
| `generate` | `workflow_id`, `content?`, `content_query?`, `template?`, `template_query?`, `template_count?`, `brand_id?`, `provider_keys?` | Execute workflow to generate content |
| `list_generated_content` | `limit?`, `offset?` | List generation history |
| `get_generated_content` | `content_id` | Get a specific generation |

### Templatize (1)
| Tool | Params | Description |
|------|--------|-------------|
| `templatize` | `content`, `model?`, `provider_key?` | Extract template from example content |

## Not Exposed via MCP

- **File upload** (`POST /source-content/upload`) — MCP tools pass structured data, not file streams. Use the REST API for file uploads, or pass extracted text via `add_source_content`.

## Tool Implementation Pattern

```python
@mcp.tool()
async def generate(
    workflow_id: str,
    content: str | None = None,
    content_query: str | None = None,
    template: str | None = None,
    template_query: str | None = None,
    template_count: int = 1,
    brand_id: str | None = None,
    provider_keys: dict | None = None,
) -> str:
    """Execute a workflow to generate social media content."""
    account = await _get_account()
    async with get_session() as db:
        # Same logic as REST /generate endpoint
        ...
        return json.dumps(result)
```

- Auth resolved once per SSE session from connection headers
- Each tool gets a fresh DB session
- Returns JSON strings
- Errors return descriptive text, not exceptions
- UUIDs accepted as strings

## SKILL.md (MCP version)

New file at `v2/skills/ghostwriter-v2-mcp/SKILL.md`:
- Same content structure as the REST skill (setup lifecycle, generation patterns, common flows)
- Framed as tool calls instead of HTTP requests
- Documents all 27 tools with params
- Notes file-upload caveat (REST-only)
- Example agent flows using tool names
