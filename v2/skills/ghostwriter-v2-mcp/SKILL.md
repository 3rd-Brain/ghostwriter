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

## What's Pre-loaded

The system ships with seed data — you can start generating immediately without setup:

**5 System Workflows** (use `list_workflows` to see them):
- **Standard Short-Form Flow (Tweets)** — 4 steps: generate → brand voice → trim to 280 chars → de-cringe
- **Atomic Essay Flow** — 2 steps: generate long-form (6-10 sentences, <250 words) → brand voice edit
- **Mid Form Flow** — 2 steps: generate mid-form → brand voice edit
- **Informal/Casual Short-Form Flow** — 3 steps: Redditor-style generation → trim → brand voice
- **Tweets-as-Templates Flow** — 4 steps: use social posts as structural templates → brand voice → trim → de-cringe

All use `claude-sonnet-4-6`. You can use these directly or create custom workflows.

**369 System Templates** (use `search_templates` to find them):
- 227 short_form, 85 atomic, 57 mid_form
- Searchable by semantic query (e.g., `search_templates(query="personal story hook")`)
- Covers: listicles, transformation stories, comparison posts, step-by-step guides, motivational hooks, industry analysis, and more

**Only brand voice and source content need to be created** before generating.

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
| `update_content_status` | `content_id`, `status` | Set review status: `new`, `approved`, `disapproved`, `posted` |

### Templatize
| Tool | Params | What it does |
|------|--------|--------------|
| `templatize` | `content`, `model?`, `provider_key?` | Extract template from example content |

## Not Available via MCP

**File upload** — Use the REST API `POST /source-content/upload` for PDF/DOCX/TXT/MD files. For text content, use the `create_source_content` or `batch_import` tools instead.

## Setup Lifecycle

The system comes with 5 workflows and 369 templates pre-loaded. You only need to add source content and a brand voice before generating. Steps 3 and 4 are optional.

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

### 3. Build templates (optional — 369 already pre-loaded)

Extract a pattern from a high-performing post, or use `search_templates` to find one that already exists:
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

### 4. Create a workflow (optional — 5 already pre-loaded)

Use `list_workflows` to see the pre-built workflows, or create a custom one:

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

### Quick start (use pre-loaded workflows + templates)

```
# 1. Pick a workflow
workflows = list_workflows()  # → choose one, e.g. "Standard Short-Form Flow (Tweets)"

# 2. Create a brand voice
brand = create_brand(name="My Brand", voice_guidelines="Direct, witty, no jargon.")

# 3. Generate using semantic search for templates
generate(
  workflow_id=workflows[0].id,
  content="Your source material here...",
  template_query="personal story hook",
  brand_id=brand.id
)
```

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
- Generated content has a `status` field: `new` → `approved` / `disapproved` / `posted` (use `update_content_status` to change)
- Token usage tracked per generation for future billing
