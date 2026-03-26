# Ghostwriter v2

AI content generation API. Ingest source content, define brand voices and multi-step LLM workflows, then generate social posts.

## Quick Start

```bash
cp .env.example .env
# Edit .env — set at least one LLM provider key (ANTHROPIC_API_KEY, OPENAI_API_KEY, or GOOGLE_API_KEY)
docker compose up
```

API is available at `http://localhost:8000`. Interactive docs at `http://localhost:8000/docs`.

## How It Works

1. **Add source content** — Import tweets, LinkedIn posts, YouTube transcripts, or upload documents
2. **Define brand voices** — Guidelines that shape the tone of generated content
3. **Create templates** — Structural patterns extracted from top-performing posts
4. **Build workflows** — Multi-step LLM pipelines (e.g., draft → refine → polish)
5. **Generate** — Execute a workflow against your content, templates, and brand voice

## Configuration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | Yes | `postgresql+asyncpg://...@db:5432/ghostwriter` | PostgreSQL connection |
| `AUTH_ENABLED` | No | `false` | Enable API-key authentication |
| `ANTHROPIC_API_KEY` | One of three | — | Claude API key |
| `OPENAI_API_KEY` | One of three | — | GPT API key (also used for embeddings) |
| `GOOGLE_API_KEY` | One of three | — | Gemini API key |
| `APIFY_API_TOKEN` | No | — | Required for social media import endpoints |
| `APIFY_LINKEDIN_ACTOR_ID` | No | (default) | Override LinkedIn scraper actor |
| `APIFY_YOUTUBE_ACTOR_ID` | No | (default) | Override YouTube scraper actor |

## Authentication

By default, auth is **disabled** — all requests use a default account. Set `AUTH_ENABLED=true` for multi-tenant mode:

```bash
# Create an account (returns API key)
curl -X POST http://localhost:8000/accounts -H "Content-Type: application/json" -d '{"name": "My Agent"}'

# Use the key
curl http://localhost:8000/brands -H "Authorization: Bearer gw_..."
```

## Agent Integration

The API exposes an OpenAPI spec at `/openapi.json` that agent frameworks can consume directly as tool definitions. Each endpoint has descriptive summaries for tool discovery.

## Supported LLM Providers

| Provider | Model Prefixes |
|----------|---------------|
| Anthropic (Claude) | `claude-*` |
| OpenAI (GPT) | `gpt-*`, `o1*`, `o3*`, `o4*` |
| Google (Gemini) | `gemini-*` |

Workflows can mix providers across steps. Keys can be set system-wide via env vars or per-request via `provider_keys` in the generate payload.
