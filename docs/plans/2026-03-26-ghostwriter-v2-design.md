# Ghostwriter V2 — System Design

## Overview

Ghostwriter V2 is a pure API/MCP service for AI-powered content generation. Agents are the only consumers — no UI. The system provides a flexible multi-step workflow engine where each step can use any supported AI model (Claude, GPT, Gemini) to generate and refine content.

The core idea: one `POST /generate` endpoint backed by user-defined workflows. Agents provide content, templates, and brand voice in whatever combination they need. The engine resolves inputs (including vector search), runs the workflow steps sequentially, and returns the output.

## Architecture

```
┌─────────────────────────────────┐
│        Docker Compose           │
│                                 │
│  ┌───────────┐  ┌────────────┐  │
│  │ Ghostwriter│  │ PostgreSQL │  │
│  │   API      │──│ + pgvector │  │
│  │ (FastAPI)  │  │            │  │
│  └───────────┘  └────────────┘  │
└─────────────────────────────────┘
```

- **Single database**: PostgreSQL + pgvector for everything (structured data, vector embeddings)
- **Stateless API**: No session state, no baked-in background tasks
- **Account-scoped**: Every piece of data belongs to an account, enforced at query level
- **Auth via API keys**: Bearer token auth, key maps to account
- **Deployment**: Docker Compose, targeting Digital Ocean droplets

## Tech Stack

- **API**: Python + FastAPI
- **Database**: PostgreSQL + pgvector
- **Migrations**: Alembic
- **AI Providers**: Anthropic (Claude), OpenAI (GPT + embeddings), Google (Gemini)
- **Containerization**: Docker Compose

## Project Structure

```
ghostwriter/
├── docker-compose.yml
├── Dockerfile
├── alembic/                  # DB migrations
├── app/
│   ├── main.py               # FastAPI app + startup
│   ├── config.py             # Settings / env vars
│   ├── auth/                 # API key auth
│   ├── models/               # SQLAlchemy models
│   ├── schemas/              # Pydantic request/response
│   ├── routers/              # Endpoint groups
│   ├── services/             # Business logic
│   ├── engine/               # Workflow execution engine
│   └── providers/            # AI provider integrations
├── tests/
└── requirements.txt
```

## Identity Model

Simple account-scoped access:

- **Account** — the single identity. Owns everything (brand voices, workflows, templates, source content).
- **Auth** — API key(s) tied to the account. Whether 1 agent or 10 agents hit the API, it's all the same account, same data.
- No formal "agent" entity — we don't care what's calling, just that it's authenticated to an account.

## Data Model

### accounts

| Column | Type | Notes |
|--------|------|-------|
| id | uuid | PK |
| name | text | |
| created_at | timestamp | |
| updated_at | timestamp | |

### api_keys

| Column | Type | Notes |
|--------|------|-------|
| id | uuid | PK |
| account_id | uuid | FK → accounts |
| key_hash | text | Hashed, never stored plain |
| label | text | e.g. "production", "dev" |
| is_active | boolean | |
| created_at | timestamp | |

### brand_voices

| Column | Type | Notes |
|--------|------|-------|
| id | uuid | PK |
| account_id | uuid | FK → accounts |
| name | text | |
| voice_guidelines | text | |
| sample_content | text | Nullable |
| created_at | timestamp | |

### workflows

| Column | Type | Notes |
|--------|------|-------|
| id | uuid | PK |
| account_id | uuid | FK → accounts, nullable (null = system workflow) |
| name | text | |
| description | text | |
| steps | jsonb | Array of step definitions |
| created_at | timestamp | |

### templates

| Column | Type | Notes |
|--------|------|-------|
| id | uuid | PK |
| account_id | uuid | FK → accounts, nullable (null = system template) |
| content | text | |
| description | text | |
| category | enum | short_form, atomic, mid_form |
| embedding | vector(1536) | pgvector |
| created_at | timestamp | |

### source_content

| Column | Type | Notes |
|--------|------|-------|
| id | uuid | PK |
| account_id | uuid | FK → accounts |
| content | text | |
| source | text | e.g. "Twitter", "uploaded_doc.pdf" |
| channel_source | text | e.g. "Twitter", "PDF", "DOCX" |
| embedding | vector(1536) | pgvector |
| metadata | jsonb | Engagement metrics, scores, etc. |
| created_at | timestamp | |

### generated_content

| Column | Type | Notes |
|--------|------|-------|
| id | uuid | PK |
| account_id | uuid | FK → accounts |
| workflow_id | uuid | FK → workflows |
| brand_id | uuid | FK → brand_voices, nullable |
| input_content | text | |
| input_template | text | Nullable |
| output | text | |
| token_usage | jsonb | Per-step breakdown |
| created_at | timestamp | |

## API Endpoints

All endpoints require `Authorization: Bearer <api_key>` header.

### Brand Voices

```
POST   /brands
GET    /brands
GET    /brands/{id}
PUT    /brands/{id}
DELETE /brands/{id}
```

### Workflows

```
POST   /workflows
GET    /workflows              # returns account + system workflows
GET    /workflows/{id}
PUT    /workflows/{id}
DELETE /workflows/{id}
```

### Templates

```
POST   /templates              # upload + auto-embed
GET    /templates
GET    /templates/{id}
POST   /templates/search       # vector similarity search
DELETE /templates/{id}
```

### Source Content

```
POST   /source-content                  # direct text + embed
POST   /source-content/upload           # file upload (PDF/DOCX/TXT/MD)
POST   /source-content/batch            # bulk import with metadata
POST   /source-content/import-twitter   # scrape Twitter/X profile via Apify
GET    /source-content
POST   /source-content/search           # vector similarity search
DELETE /source-content/{id}
```

### Generation

```
POST /generate
{
  "workflow_id": "uuid",                  // required — which pipeline to run

  // Content input — provide one or both:
  "content": "string",                    // direct content
  "content_query": "string",             // OR semantic search for source content

  // Template input — all optional:
  "template": "string",                   // direct template
  "template_query": "string",            // OR semantic search for a template
  "template_count": 1,                    // number of templates (= number of outputs)

  // Context:
  "brand_id": "uuid",                     // optional brand voice to apply

  // AI provider config:
  "provider_keys": {                      // optional — use account keys or system fallback
    "anthropic": "sk-...",
    "openai": "sk-...",
    "google": "..."
  }
}
```

**Response:**
```json
{
  "generations": [
    {
      "id": "uuid",
      "output": "generated content string",
      "template_used": "...",
      "token_usage": {
        "steps": [
          {"step": 1, "model": "claude-sonnet-4-20250514", "input_tokens": 500, "output_tokens": 200}
        ],
        "total_tokens": 700
      }
    }
  ]
}
```

### Templatize

```
POST /templatize
{
  "content": "a concrete social post"
}
→ { "template": "extracted template with [placeholders]" }
```

### Generated Content (read-only history)

```
GET    /generated-content
GET    /generated-content/{id}
```

## Workflow Engine

The engine executes workflow steps sequentially. Each step is an AI model call with variable substitution.

### Execution Flow

```
Request hits /generate
    │
    ├── 1. Resolve inputs
    │     ├── If content_query → vector search source_content, get top match(es)
    │     ├── If template_query → vector search templates, get top N
    │     ├── If brand_id → fetch brand voice guidelines
    │     └── Validate workflow_id, load step definitions
    │
    ├── 2. Build generation context
    │     { content, template, brand_voice }
    │
    ├── 3. Execute workflow steps sequentially
    │     Step 1: substitute variables → call AI model → get output
    │     Step 2: {prev_ai_output} = Step 1's output → call AI → get output
    │     Step 3: {prev_ai_output} = Step 2's output → call AI → get output
    │     ...
    │
    ├── 4. If template_count > 1, repeat steps 1-3 per template
    │
    └── 5. Record to generated_content table with token usage
```

### Step Definition Schema

Stored as JSONB in `workflows.steps`:

```json
[
  {
    "order": 1,
    "name": "initial_generation",
    "model": "claude-sonnet-4-20250514",
    "system_prompt": "You are a social media writer...",
    "user_prompt": "Using this template: {template}\n\nSource: {content}\n\nBrand voice: {brand_voice}",
    "max_tokens": 4096,
    "temperature": 0.7
  },
  {
    "order": 2,
    "name": "brand_voice_edit",
    "model": "claude-haiku-4-5-20251001",
    "system_prompt": "Refine this post to match the brand voice...",
    "user_prompt": "Post: {prev_ai_output}\n\nBrand voice: {brand_voice}",
    "max_tokens": 2048,
    "temperature": 0.4
  }
]
```

### Template Variables

Auto-substituted before each step:
- `{content}` — resolved source content
- `{template}` — resolved template
- `{brand_voice}` — brand guidelines
- `{prev_ai_output}` — output of the previous step

### Provider Layer

```
app/providers/
├── base.py          # shared interface: generate(model, system_prompt, user_prompt, max_tokens, temperature) → string
├── anthropic.py     # Claude models
├── openai.py        # GPT models (+ embeddings)
└── google.py        # Gemini models
```

The engine resolves the model string to the right provider. Each step in a workflow can use a different provider. The provider layer maps model identifiers to SDK calls.

## AI Provider Keys

Dual-mode key handling:
- If `provider_keys` is provided in the request, those keys are used for that request only
- If omitted, the system falls back to system-managed keys
- Only keys for providers actually used in the workflow steps need to be present
- Token usage is tracked per generation regardless of key source (for future billing)

## File Upload Pipeline

```
POST /source-content/upload → extract text → chunk → embed → store
```

- Supported: PDF, DOCX, TXT, MD
- No object storage — raw files are not kept, only extracted chunked text
- Chunk size configurable (default ~500 tokens)
- Embeddings via OpenAI text-embedding-3-small

## Twitter/X Import

```
POST /source-content/import-twitter
{
  "profile_url": "https://x.com/handle",
  "max_tweets": 50
}
```

- Calls Apify Twitter scraper
- Extracts tweets with engagement metrics
- Calculates weighted engagement scores
- Embeds and stores as source content with metrics in metadata JSONB
- Agents can later search source content and sort/filter by engagement scores in metadata

## Publication Tracking

No dedicated publication subsystem. Instead, agents push published content back into `/source-content` or `/source-content/batch` with engagement metrics in the `metadata` field. Vector search + metadata filtering achieves "find my best performing content about X" without a separate system.

## Out of Scope (for now)

- **No UI** — pure API/MCP
- **No credit/billing system** — token_usage tracked per generation for future use
- **No industry reports** — the n8n webhook integration from V1
- **No onboarding flow** — account creation is a simple API call

## Migration Notes

The current V1 system stores data in AstraDB. Key collections and their V2 equivalents:

| V1 (AstraDB) | V2 (PostgreSQL) |
|---|---|
| user_content_keyspace/brands | brand_voices table |
| sys_keyspace/workflows + user_content_keyspace/user_workflows | workflows table (nullable account_id) |
| sys_keyspace/templates + user_content_keyspace/user_templates | templates table (nullable account_id) |
| user_content_keyspace/user_source_content | source_content table |
| user_content_keyspace/generated_content | generated_content table |
| user_content_keyspace/user_twitter_publications | source_content table (with engagement metadata) |
