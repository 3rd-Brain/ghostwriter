---
name: ghostwriter-v2-api
description: Use when generating social media content, managing brand voices, working with content templates, importing source material, or calling any Ghostwriter V2 endpoint. Reference for all API operations, input resolution modes, and multi-step workflow execution.
---

# Ghostwriter V2 API

AI-powered content generation engine. You provide source content, brand voice, templates, and a workflow recipe — it runs a multi-step LLM pipeline and returns generated posts.

## Auth

Every request requires `Authorization: Bearer <api_key>`.

```
POST /accounts  {"name": "Acme Corp"}
→ { "account": {...}, "api_key": "gw_abc123..." }   ← shown once, save it
```

After this, all data is scoped to your account. You cannot see or modify another account's resources.

## Resource Model

Five resource pools, one action endpoint:

```
Brand Voices ─── "how to sound"
Workflows    ─── "multi-step AI recipes"        ──→  POST /generate  ──→  Generated Content
Templates    ─── "structural patterns"                  (the engine)        (read-only history)
Source Content ── "raw material (vector-embedded)"
```

## What's Pre-loaded

The system ships with seed data — you can start generating immediately:

**5 System Workflows** (`GET /workflows`):

- **Standard Short-Form Flow (Tweets)** — 4 steps: generate → brand voice → trim to 280 chars → de-cringe
- **Atomic Essay Flow** — 2 steps: generate long-form (6-10 sentences, <250 words) → brand voice edit
- **Mid Form Flow** — 2 steps: generate mid-form → brand voice edit
- **Informal/Casual Short-Form Flow** — 3 steps: Redditor-style generation → trim → brand voice
- **Tweets-as-Templates Flow** — 4 steps: use social posts as structural templates → brand voice → trim → de-cringe

All use `claude-sonnet-4-6`. Use these directly or create custom workflows.

**369 System Templates** (`POST /templates/search`):

- 227 short_form, 85 atomic, 57 mid_form
- Searchable by semantic query (e.g., `{"query": "personal story hook"}`)
- Covers: listicles, transformation stories, comparison posts, step-by-step guides, motivational hooks, industry analysis, and more

**Only brand voice and source content need to be created** before generating.

## Endpoints Quick Reference

| Resource | Create | List | Get | Update | Delete | Search |
|----------|--------|------|-----|--------|--------|--------|
| Accounts | `POST /accounts` | — | `GET /accounts/me` | — | — | — |
| Brands | `POST /brands` | `GET /brands` | `GET /brands/{id}` | `PUT /brands/{id}` | `DELETE /brands/{id}` | — |
| Workflows | `POST /workflows` | `GET /workflows` | `GET /workflows/{id}` | `PUT /workflows/{id}` | `DELETE /workflows/{id}` | — |
| Templates | `POST /templates` | `GET /templates` | `GET /templates/{id}` | — | `DELETE /templates/{id}` | `POST /templates/search` |
| Source Content | `POST /source-content` | `GET /source-content` | — | — | `DELETE /source-content/{id}` | `POST /source-content/search` |
| Generated Content | — | `GET /generated-content` | `GET /generated-content/{id}` | `PATCH /generated-content/{id}/status` | — | — |

Special endpoints:
- `POST /source-content/batch` — bulk import with metadata
- `POST /source-content/upload` — file upload (PDF/DOCX/TXT/MD) → extract → chunk → embed
- `POST /source-content/import-twitter` — scrape Twitter/X profile via Apify, score engagement, embed
- `POST /source-content/import-linkedin` — scrape LinkedIn profile posts via Apify, score engagement, embed
- `POST /source-content/import-youtube/channel` — scrape YouTube channel videos + transcripts via Apify, embed
- `POST /source-content/import-youtube/video` — extract single YouTube video transcript via Apify, embed
- `POST /generate` — run a workflow against resolved inputs
- `POST /templatize` — extract structural template from a concrete post
- `PATCH /generated-content/{id}/status` — set review status (`new`, `approved`, `disapproved`, `posted`)

## Setup Lifecycle

The system comes with 5 workflows and 369 templates pre-loaded. You only need to add source content and a brand voice before generating. Steps 3 and 4 are optional.

### 1. Import source content (your raw material)

```json
// Direct text
POST /source-content
{ "content": "AI is transforming healthcare by...", "source": "blog" }

// Bulk import
POST /source-content/batch
{ "items": [
    {"content": "First piece", "source": "newsletter"},
    {"content": "Second piece", "source": "blog", "metadata": {"score": 9.2}}
]}

// File upload (PDF, DOCX, TXT, MD) — auto-chunked and embedded
POST /source-content/upload  [multipart form: file]

// Twitter scrape — auto-scores engagement, embeds
POST /source-content/import-twitter
{ "profile_url": "https://x.com/handle", "max_tweets": 50 }

// LinkedIn scrape — posts with engagement metrics
POST /source-content/import-linkedin
{ "profile_url": "https://linkedin.com/in/handle", "max_posts": 50 }

// YouTube channel — videos with transcripts
POST /source-content/import-youtube/channel
{ "channel_url": "https://youtube.com/@channel", "max_videos": 20, "sort_by": "POPULAR" }

// YouTube single video — transcript extraction
POST /source-content/import-youtube/video
{ "video_url": "https://youtube.com/watch?v=abc123" }
```

All source content is automatically vector-embedded for semantic search later. All scrapers use Apify and require `APIFY_API_TOKEN`.

### 2. Define brand voice

```json
POST /brands
{
  "name": "CEO Thought Leadership",
  "voice_guidelines": "Authoritative but approachable. Short sentences. No jargon. First person.",
  "sample_content": "Optional example posts showing the voice in action..."
}
```

Create multiple brands for different contexts (LinkedIn vs Twitter, CEO vs company page, etc.)

### 3. Build templates (optional — 369 already pre-loaded)

Extract a structural pattern from a high-performing post:

```json
POST /templatize
{ "content": "I spent 10 years building startups and here's the truth..." }
→ { "template": "I spent [X time] [doing activity] and here's [the insight]..." }
```

Then store it:

```json
POST /templates
{
  "content": "I spent [X time] [doing activity] and here's [the insight]...",
  "description": "Personal experience hook — strong opener for thought leadership",
  "category": "short_form"
}
```

Templates are vector-embedded too. Categories: `short_form`, `atomic`, `mid_form`.

### 4. Create a workflow (optional — 5 already pre-loaded)

A workflow is an ordered list of LLM steps. Each step can use a different model. Output chains via `{prev_ai_output}`.

```json
POST /workflows
{
  "name": "LinkedIn Thought Leadership",
  "description": "Two-pass: creative draft then brand voice refinement",
  "steps": [
    {
      "order": 1,
      "name": "draft",
      "model": "claude-sonnet-4-20250514",
      "system_prompt": "You are a social media ghostwriter...",
      "user_prompt": "Source material:\n{content}\n\nTemplate to follow:\n{template}\n\nBrand voice:\n{brand_voice}",
      "max_tokens": 4096,
      "temperature": 0.7
    },
    {
      "order": 2,
      "name": "refine",
      "model": "claude-haiku-4-5-20251001",
      "system_prompt": "Tighten this post. Match the brand voice exactly. Remove filler.",
      "user_prompt": "Draft:\n{prev_ai_output}\n\nBrand voice to match:\n{brand_voice}",
      "max_tokens": 2048,
      "temperature": 0.4
    }
  ]
}
```

**Available template variables** (auto-substituted before each step):

| Variable | Value |
|----------|-------|
| `{content}` | Resolved source content |
| `{template}` | Resolved template |
| `{brand_voice}` | Brand voice guidelines |
| `{prev_ai_output}` | Previous step's output (empty string on step 1) |

**Supported models** (resolved by prefix):
- `claude-*` → Anthropic
- `gpt-*`, `o1*`, `o3*`, `o4*` → OpenAI
- `gemini-*` → Google

## Generation (the main event)

```json
POST /generate
{
  "workflow_id": "uuid",

  // Content — pick one:
  "content": "direct text",              // OR
  "content_query": "AI in healthcare",   // → semantic search, top 3 matches joined

  // Template — pick one (or omit):
  "template": "I spent [X]...",          // OR
  "template_query": "personal story",    // → semantic search
  "template_count": 3,                   // how many templates = how many outputs

  // Brand voice (optional):
  "brand_id": "uuid",

  // API keys (optional — falls back to system keys):
  "provider_keys": {
    "anthropic": "sk-...",
    "openai": "sk-...",
    "google": "..."
  }
}
```

### Input resolution modes

| Input | Direct | Semantic search |
|-------|--------|-----------------|
| Content | `"content": "raw text"` | `"content_query": "topic"` → top 3 source content matches by vector similarity |
| Template | `"template": "pattern text"` | `"template_query": "hook style"` → top N templates by vector similarity |
| Brand | `"brand_id": "uuid"` | Always by ID |

### What happens inside `/generate`

```
1. Load workflow steps
2. Resolve content (direct text or vector search over source_content)
3. Resolve brand voice guidelines
4. Resolve templates (direct, vector search, or none)
5. For EACH template:
   a. Build context: {content, template, brand_voice, prev_ai_output: ""}
   b. Execute steps in order:
      Step 1 → substitute variables → call LLM → capture output
      Step 2 → {prev_ai_output} = Step 1 output → call LLM → capture
      Step N → ...
   c. Save to generated_content with token usage
6. Return all generations
```

`template_count: 3` = find 3 templates, run the full workflow 3 times, return 3 structurally different outputs from the same source content.

### Response

```json
{
  "generations": [
    {
      "id": "uuid",
      "output": "The generated post text...",
      "template_used": "I spent [X time]...",
      "token_usage": {
        "steps": [
          {"step": 1, "name": "draft", "model": "claude-sonnet-4-20250514", "input_tokens": 800, "output_tokens": 400},
          {"step": 2, "name": "refine", "model": "claude-haiku-4-5-20251001", "input_tokens": 500, "output_tokens": 200}
        ],
        "total_tokens": 1900
      }
    }
  ]
}
```

## Common Agent Patterns

### Generate with full control (all inputs explicit)

```json
POST /generate
{
  "workflow_id": "wf-uuid",
  "content": "Here is the exact source text to use...",
  "template": "I spent [X time] [doing thing]...",
  "brand_id": "brand-uuid"
}
```

### Generate hands-off (let vector search find everything)

```json
POST /generate
{
  "workflow_id": "wf-uuid",
  "content_query": "artificial intelligence healthcare",
  "template_query": "personal story hook",
  "template_count": 3,
  "brand_id": "brand-uuid"
}
```

### Generate without template (free-form)

```json
POST /generate
{
  "workflow_id": "wf-uuid",
  "content": "Source material here...",
  "brand_id": "brand-uuid"
}
```

When no template is provided, `{template}` resolves to empty string. Design your workflow prompts to handle this gracefully.

### Templatize a viral post then generate with it

```json
// 1. Extract template
POST /templatize
{ "content": "Saw a viral post text here..." }
→ { "template": "extracted [placeholder] pattern..." }

// 2. Store it
POST /templates
{ "content": "extracted [placeholder] pattern...", "description": "viral hook", "category": "short_form" }

// 3. Generate using it
POST /generate
{ "workflow_id": "wf-uuid", "content_query": "my topic", "template": "extracted [placeholder] pattern...", "brand_id": "brand-uuid" }
```

### Daily content automation loop

```text
1. POST /source-content/import-twitter          — scrape fresh tweets
2. POST /source-content/import-linkedin         — scrape LinkedIn posts
3. POST /source-content/import-youtube/channel  — scrape new videos + transcripts
4. POST /source-content/batch                   — import blog posts / newsletters
5. POST /generate                               — content_query + brand voice + workflow
6. GET  /generated-content                      — review outputs
7. (publish via external tool — Ghostwriter only generates, never publishes)
```

## Errors

| Status | Meaning |
|--------|---------|
| 401 | Missing or invalid API key |
| 404 | Resource not found or belongs to another account |
| 422 | Validation error (check request body) |
| 500 | Server error (likely LLM provider failure — check which workflow step failed) |

## Key Constraints

- Ghostwriter **generates only** — it does not publish, schedule, or track analytics
- All data is account-scoped — you only see your own resources
- Source content and templates are vector-embedded at creation time — you cannot update them, only delete and recreate
- Workflows can mix models across steps (e.g., Sonnet for drafting, Haiku for polish)
- `provider_keys` in generate requests are per-request only, not stored
- Generated content has a `status` field: `new` → `approved` / `disapproved` / `posted` (use `PATCH /generated-content/{id}/status`)
- Token usage is tracked per generation for future billing but no credit system exists yet
