# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Ghostwriter is a SaaS social media content generation platform. Users provide source content (tweets, documents), brand voice profiles, and templates; the system uses LLMs (Anthropic Claude, OpenAI GPT) to generate short-form social posts. Built as a FastAPI monolith, originally developed and deployed on Replit.

## Running the App

```bash
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --reload
```

Production deployment (Replit/Cloud Run): `uvicorn main:app --host 0.0.0.0 --port 8080`

### Admin Scripts

```bash
python admin_scripts/pricing_config_manager.py   # Manage credit pricing
python admin_scripts/credit_system_tester.py      # Test credit system
```

## Architecture

### Dual Database System
- **AstraDB (DataStax)**: Primary data store for users, brand voices, source content, generated content, templates, workflow configs, publications, and API keys. Accessed via REST API (`requests.post` to JSON API endpoints), not an ORM. Collections live in keyspaces like `users_keyspace`, `user_content_keyspace`.
- **PostgreSQL**: Transaction logging for the credit system only. Accessed via `psycopg2` through `credit_system/postgres_setup.py`.

### Authentication (Dual Mode)
- **Browser/UI**: JWT tokens stored in cookies. `main.py:get_current_user` dependency validates JWT from cookies.
- **API**: API keys via `X-API-Key` header. `api_middleware.py` provides `get_current_api_user` and `check_api_key_or_jwt` (accepts either auth method).
- API keys use `GW_` prefix, are bcrypt-hashed before storage, and encrypted with Fernet (`third_party_keys.py`).

### Content Generation Pipeline
1. **Source Content** (`source_content_manager.py`): Ingests tweets/documents, generates OpenAI embeddings, stores in AstraDB.
2. **Brand Voice** (`brand_management.py`): Analyzes social posts via LLM to produce brand voice guides.
3. **Templates** (`social_writer.py` → `Templatizer`): Extracts structural patterns from top-performing posts.
4. **Generation** (`social_writer.py`, `social_dynamic_generation_flow.py`): Two generation paths:
   - Direct generation: `short_form_social_repurposing`, `repurposer_using_posts_as_templates`
   - Flow-based generation: `social_post_generation_with_json` executes multi-step LLM workflows defined in JSON configs (stored in AstraDB `generation_flows` collection). Each step chains prompts with variable substitution (`$prev_output`, `$client_brief`, etc.).
5. **Publishing** (`publish_history_manager.py`): Tracks publication history and metrics.

### Credit System (`credit_system/`)
- `credit_manager.py`: Core logic — validates balance, reserves credits, deducts after generation, estimates costs.
- `credit_database_manager.py`: DB operations (AstraDB for balances, PostgreSQL for transactions).
- `credit_transaction_logger.py`: Audit logging.
- `pricing_config.json`: Per-model token costs with markup percentage. Updated via admin script.
- `token_tracker.py`: Tracks actual token usage per LLM call.

### Web Scraping (`scrapers.py`)
Uses Apify API for LinkedIn and Twitter/X scraping. Requires `APIFY_API_TOKEN` env var.

### Third-Party API Keys (`third_party_keys.py`)
Users store their own OpenAI/Anthropic API keys. Keys are Fernet-encrypted (using `ENCRYPTION_KEY` env var) before storage in AstraDB.

### Routing Structure
- `main.py`: App setup, auth routes, HTML page routes, and most API endpoints (large file).
- `api_routes.py`: Additional API endpoints under `/api` prefix.
- `scraper_routes.py`: Scraping-related API endpoints.
- `api_key_routes.py`: API key management endpoints.
- `onboarding.py`: User onboarding flow (mounted as router).
- `brand_management.py`: Brand CRUD (mounted as router).

### Frontend
Server-rendered HTML via Jinja2 templates (`templates/`) with static JS/CSS (`static/`). Uses Lucide icons. Key pages: dashboard, brand management, content generation, template management, workflow management, source content, industry reports, publish history, settings.

### LLM Prompt System
All prompt templates centralized in `prompts.py` as class attributes on `Prompts`. Uses XML-tagged sections (`<ACTION>`, `<PERSONA>`, `<CONSTRAINTS>`).

## Key Environment Variables

- `ASTRA_DB_API_ENDPOINT`, `ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER` — AstraDB access
- `JWT_SECRET_KEY` — JWT signing
- `ENCRYPTION_KEY` — Fernet key for encrypting stored third-party API keys
- `APIFY_API_TOKEN` — Web scraping via Apify
- `DATABASE_URL` — PostgreSQL connection (credit system)
- `REPLIT_OBJECT_STORAGE_*` — Replit object storage for document uploads

## Patterns to Know

- AstraDB operations follow a consistent pattern: build a URL like `{ASTRA_DB_API_ENDPOINT}/api/json/v1/{keyspace}/{collection}`, POST a JSON command (`findOne`, `find`, `insertOne`, `findOneAndUpdate`, etc.) with `Token` header.
- User-scoped data always filters by `user_id` field.
- LLM clients are instantiated per-request using the user's own API keys (not a shared key).
- The `document_processor.py` uses Replit Object Storage (`replit.object_storage.Client`) for file uploads and PyMuPDF for PDF extraction.
